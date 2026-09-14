"""
Regression tests for late topup recovery remediation ([CRIT-01]).

Verifies that an auto-cancelled topup receiving a PayOS IPN:
1. Atomically transitions from CANCELLED -> PAID.
2. Credits the user's wallet balance properly.
3. Records a BalanceTransaction audit record with kind=TOPUP.
4. Is completely idempotent on duplicate IPN delivery.
5. In IPNProcessor, sends the late-recovery notification to the user and alerts the admin.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    BalanceTransaction,
    BalanceTxKind,
    Base,
    BotUser,
    TopupOrder,
    TopupStatus,
)
from src.database.services.balance_service import BalanceService
from src.ipn.processor import IPNOrderProcessor


@pytest.fixture
def session_factory(tmp_path):
    db_url = f"sqlite:///{tmp_path}/late_topup_test.db"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_credit_topup_reactivates_cancelled_status(session_factory):
    """Test that credit_topup atomically transitions CANCELLED topup to PAID and credits balance."""
    session = session_factory()
    try:
        user = BotUser(
            telegram_user_id=111001,
            username="test_late_topup_user",
            balance=10_000,
        )
        session.add(user)
        session.commit()

        topup = TopupOrder(
            id="TU_CANCELLED_01",
            user_id=user.telegram_user_id,
            bot_user_id=user.id,
            amount=50_000,
            status=TopupStatus.CANCELLED,
        )
        session.add(topup)
        session.commit()

        svc = BalanceService(session)
        success, reason = svc.credit_topup("TU_CANCELLED_01", "tx_payos_123")

        assert success is True
        assert reason == "reactivated_cancelled"

        # Verify DB state
        session.refresh(topup)
        assert topup.status == TopupStatus.PAID
        assert topup.payment_transaction_id == "tx_payos_123"

        session.refresh(user)
        assert user.balance == 60_000

        # Verify BalanceTransaction created
        txns = (
            session.execute(
                select(BalanceTransaction).where(
                    BalanceTransaction.reference_id == "TU_CANCELLED_01"
                )
            )
            .scalars()
            .all()
        )
        assert len(txns) == 1
        assert txns[0].kind == BalanceTxKind.TOPUP
        assert txns[0].amount == 50_000
        assert txns[0].balance_after == 60_000

        # Test duplicate call is idempotent
        success2, reason2 = svc.credit_topup("TU_CANCELLED_01", "tx_payos_duplicate")
        assert success2 is False
        assert reason2 == "already_processed"

        session.refresh(user)
        assert user.balance == 60_000
    finally:
        session.close()


def test_ipn_processor_handles_late_topup(session_factory):
    """Test full IPNProcessor flow when processing a late payment for an auto-cancelled topup."""
    session = session_factory()
    try:
        user = BotUser(
            telegram_user_id=111002,
            username="test_ipn_late_user",
            balance=0,
        )
        session.add(user)
        session.commit()

        topup = TopupOrder(
            id="TU_CANCELLED_02",
            user_id=user.telegram_user_id,
            bot_user_id=user.id,
            amount=100_000,
            status=TopupStatus.CANCELLED,
        )
        session.add(topup)
        session.commit()
    finally:
        session.close()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.delete_message = AsyncMock()

    with patch("src.ipn.processor.get_session_factory", return_value=session_factory):
        processor = IPNOrderProcessor(bot=mock_bot)

    # First delivery — should reactivate, credit balance, and notify user
    result = processor.process_payment_success(
        order_id="TU_CANCELLED_02",
        transaction_id="payos_tx_999",
        amount=100_000,
    )
    assert result is True

    verify_session = session_factory()
    try:
        topup_row = (
            verify_session.execute(
                select(TopupOrder).where(TopupOrder.id == "TU_CANCELLED_02")
            )
            .scalars()
            .one()
        )
        assert topup_row.status == TopupStatus.PAID

        user_row = (
            verify_session.execute(
                select(BotUser).where(BotUser.telegram_user_id == 111002)
            )
            .scalars()
            .one()
        )
        assert user_row.balance == 100_000
    finally:
        verify_session.close()

    # User notification was called with late recovery text
    assert mock_bot.send_message.call_count >= 1
    call_args_list = mock_bot.send_message.call_args_list
    user_notifications = [
        call.kwargs.get("text", "")
        for call in call_args_list
        if call.kwargs.get("chat_id") == 111002
    ]
    assert any("khôi phục" in text for text in user_notifications)

    # Second delivery — duplicate IPN should return True and not double credit
    result_dup = processor.process_payment_success(
        order_id="TU_CANCELLED_02",
        transaction_id="payos_tx_999_dup",
        amount=100_000,
    )
    assert result_dup is True

    verify_session2 = session_factory()
    try:
        user_row2 = (
            verify_session2.execute(
                select(BotUser).where(BotUser.telegram_user_id == 111002)
            )
            .scalars()
            .one()
        )
        assert user_row2.balance == 100_000
    finally:
        verify_session2.close()
