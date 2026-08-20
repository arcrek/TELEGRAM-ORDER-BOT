"""
Concurrency tests for BalanceService atomic wallet operations.

Verifies that race conditions on pay_order_with_balance, credit_topup,
and adjust(subtract) are all handled correctly by the atomic
conditional-UPDATE pattern.

Uses file-based SQLite (each thread gets its own connection) so the
database-locked serialisation is realistic enough to catch logical errors,
even though SQLite serialises writes at the OS level.
"""
import threading

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Import all models so Base.metadata is fully populated before create_all.
from src.database.models import (
    Admin,
    AdminRole,
    BalanceTransaction,
    BalanceTxKind,
    Base,
    BotUser,
    Order,
    OrderStatus,
    TopupOrder,
    TopupStatus,
)
from src.database.services.balance_service import BalanceService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_url(tmp_path):
    """File-based SQLite URL so each connection goes through the real file locking."""
    return f"sqlite:///{tmp_path}/balance_test.db"


@pytest.fixture
def session_factory(db_url):
    """
    Create all tables and return a sessionmaker that every thread can call
    independently to get its own Session (and therefore its own connection).
    """
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def test_admin(session_factory):
    """Minimal Admin row — required for BalanceService.adjust FK."""
    session = session_factory()
    try:
        admin = Admin(
            id="admin-test-001",
            username="testadmin",
            password_hash="x",
            full_name="Test Admin",
            role=AdminRole.ADMIN,
        )
        session.add(admin)
        session.commit()
        return admin.id
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helper to build a minimal Order row
# ---------------------------------------------------------------------------

def _make_order(session, order_id: str, user: BotUser, amount: int) -> Order:
    order = Order(
        id=order_id,
        user_id=user.telegram_user_id,
        status=OrderStatus.PENDING,
        total_amount=amount,
    )
    session.add(order)
    session.commit()
    return order


# ---------------------------------------------------------------------------
# Test A — two different orders, insufficient combined balance
# ---------------------------------------------------------------------------

class TestTwoDifferentOrdersInsufficientBalance:
    """
    BotUser has 10_000 VND.
    Two orders each need 10_000 VND.
    Exactly one must succeed; the other must be refused for 'insufficient'.
    """

    def test_exactly_one_succeeds(self, session_factory):
        setup_session = session_factory()
        try:
            user = BotUser(
                telegram_user_id=100001,
                username="user_a",
                balance=10_000,
            )
            setup_session.add(user)
            setup_session.commit()
            bot_user_id = user.id
            user_telegram_id = user.telegram_user_id

            _make_order(setup_session, "ORD-A-001", user, 10_000)
            _make_order(setup_session, "ORD-A-002", user, 10_000)
        finally:
            setup_session.close()

        results = []
        barrier = threading.Barrier(2)

        def worker(order_id: str) -> None:
            session = session_factory()
            try:
                # Load BotUser fresh inside this thread's session.
                bot_user = session.execute(
                    select(BotUser).where(BotUser.id == bot_user_id)
                ).scalar_one()
                barrier.wait()  # Start both threads at the same moment.
                svc = BalanceService(session)
                result = svc.pay_order_with_balance(order_id, bot_user)
                results.append(result)
            finally:
                session.close()

        t1 = threading.Thread(target=worker, args=("ORD-A-001",))
        t2 = threading.Thread(target=worker, args=("ORD-A-002",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 2

        successes = [r for r in results if r[0] is True]
        failures = [r for r in results if r[0] is False]

        assert len(successes) == 1, f"Expected 1 success, got: {results}"
        assert len(failures) == 1, f"Expected 1 failure, got: {results}"
        assert failures[0][1] == "insufficient", f"Expected 'insufficient', got: {failures[0][1]}"

        # Verify DB state using a fresh read session.
        verify = session_factory()
        try:
            final_balance = verify.execute(
                select(BotUser.balance).where(BotUser.id == bot_user_id)
            ).scalar_one()
            assert final_balance == 0, f"Expected balance=0, got {final_balance}"

            paid_orders = verify.execute(
                select(Order).where(
                    Order.user_id == user_telegram_id,
                    Order.status == OrderStatus.PAID,
                )
            ).scalars().all()
            assert len(paid_orders) == 1, f"Expected 1 PAID order, got {len(paid_orders)}"

            txns = verify.execute(
                select(BalanceTransaction).where(
                    BalanceTransaction.bot_user_id == bot_user_id,
                    BalanceTransaction.kind == BalanceTxKind.ORDER_PAYMENT,
                )
            ).scalars().all()
            assert len(txns) == 1, f"Expected 1 ORDER_PAYMENT txn, got {len(txns)}"
        finally:
            verify.close()


# ---------------------------------------------------------------------------
# Test B — same order paid twice (double-tap)
# ---------------------------------------------------------------------------

class TestSameOrderPaidTwice:
    """
    BotUser has 20_000 VND (surplus), order costs 10_000.
    Two threads try to pay the same order concurrently.
    Exactly one should succeed; the other must get 'already_processed'.
    Balance deducted exactly once.
    """

    def test_double_tap_idempotent(self, session_factory):
        setup_session = session_factory()
        try:
            user = BotUser(
                telegram_user_id=100002,
                username="user_b",
                balance=20_000,
            )
            setup_session.add(user)
            setup_session.commit()
            bot_user_id = user.id
            _make_order(setup_session, "ORD-B-001", user, 10_000)
        finally:
            setup_session.close()

        results = []
        barrier = threading.Barrier(2)

        def worker() -> None:
            session = session_factory()
            try:
                bot_user = session.execute(
                    select(BotUser).where(BotUser.id == bot_user_id)
                ).scalar_one()
                barrier.wait()
                svc = BalanceService(session)
                result = svc.pay_order_with_balance("ORD-B-001", bot_user)
                results.append(result)
            finally:
                session.close()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 2

        successes = [r for r in results if r[0] is True]
        failures = [r for r in results if r[0] is False]

        assert len(successes) == 1, f"Expected 1 success, got: {results}"
        assert len(failures) == 1, f"Expected 1 failure, got: {results}"
        assert failures[0][1] == "already_processed", (
            f"Expected 'already_processed', got: {failures[0][1]}"
        )

        verify = session_factory()
        try:
            final_balance = verify.execute(
                select(BotUser.balance).where(BotUser.id == bot_user_id)
            ).scalar_one()
            assert final_balance == 10_000, (
                f"Expected balance=10_000 (deducted once), got {final_balance}"
            )

            order_row = verify.execute(
                select(Order).where(Order.id == "ORD-B-001")
            ).scalar_one()
            assert order_row.status == OrderStatus.PAID

            txns = verify.execute(
                select(BalanceTransaction).where(
                    BalanceTransaction.bot_user_id == bot_user_id,
                )
            ).scalars().all()
            assert len(txns) == 1, f"Expected exactly 1 BalanceTransaction, got {len(txns)}"
        finally:
            verify.close()


# ---------------------------------------------------------------------------
# Test C — admin subtract guards against negative balance
# ---------------------------------------------------------------------------

class TestAdminSubtractGuardsNegative:
    """
    BotUser has 5_000 VND.
    Admin tries to subtract 10_000 — should fail with 'insufficient'.
    Balance must stay 5_000. No BalanceTransaction row created.
    """

    def test_subtract_insufficient(self, session_factory, test_admin):
        session = session_factory()
        try:
            user = BotUser(
                telegram_user_id=100003,
                username="user_c",
                balance=5_000,
            )
            session.add(user)
            session.commit()
            bot_user_id = user.id

            svc = BalanceService(session)
            success, code, new_balance = svc.adjust(
                bot_user_id=bot_user_id,
                action="subtract",
                amount=10_000,
                admin_id=test_admin,
                reason="test subtract over balance",
            )

            assert success is False
            assert code == "insufficient"
            # new_balance returned on failure is 0 per service contract
            assert new_balance == 0

            # Verify the actual balance is still 5_000.
            actual = session.execute(
                select(BotUser.balance).where(BotUser.id == bot_user_id)
            ).scalar_one()
            assert actual == 5_000, f"Expected balance=5_000, got {actual}"

            # No BalanceTransaction should have been created.
            txns = session.execute(
                select(BalanceTransaction).where(
                    BalanceTransaction.bot_user_id == bot_user_id
                )
            ).scalars().all()
            assert len(txns) == 0, f"Expected 0 BalanceTransactions, got {len(txns)}"
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Test D — topup credit is idempotent (bonus)
# ---------------------------------------------------------------------------

class TestTopupCreditIdempotent:
    """
    Call credit_topup twice with the same topup_id.
    First call: (True, 'ok'), balance credited once.
    Second call: (False, 'already_processed'), balance unchanged.
    Exactly one BalanceTransaction row.
    """

    def test_idempotent_topup(self, session_factory):
        session = session_factory()
        try:
            user = BotUser(
                telegram_user_id=100004,
                username="user_d",
                balance=0,
            )
            session.add(user)
            session.commit()
            bot_user_id = user.id

            topup = TopupOrder(
                id="TUtest0001",
                user_id=user.telegram_user_id,
                bot_user_id=bot_user_id,
                amount=100_000,
                status=TopupStatus.PENDING,
            )
            session.add(topup)
            session.commit()

            svc = BalanceService(session)

            # First call — should succeed.
            ok1, reason1 = svc.credit_topup("TUtest0001", "tx-id-1")
            assert ok1 is True, f"First credit_topup failed: {reason1}"
            assert reason1 == "ok"

            balance_after_first = session.execute(
                select(BotUser.balance).where(BotUser.id == bot_user_id)
            ).scalar_one()
            assert balance_after_first == 100_000, (
                f"Expected balance=100_000 after first topup, got {balance_after_first}"
            )

            # Second call — must be idempotent.
            ok2, reason2 = svc.credit_topup("TUtest0001", "tx-id-2")
            assert ok2 is False, "Second credit_topup should have failed but got ok"
            assert reason2 == "already_processed"

            balance_after_second = session.execute(
                select(BotUser.balance).where(BotUser.id == bot_user_id)
            ).scalar_one()
            assert balance_after_second == 100_000, (
                f"Balance should still be 100_000, got {balance_after_second}"
            )

            # Exactly one BalanceTransaction should exist.
            txns = session.execute(
                select(BalanceTransaction).where(
                    BalanceTransaction.bot_user_id == bot_user_id
                )
            ).scalars().all()
            assert len(txns) == 1, f"Expected exactly 1 BalanceTransaction, got {len(txns)}"
            assert txns[0].kind == BalanceTxKind.TOPUP
        finally:
            session.close()
