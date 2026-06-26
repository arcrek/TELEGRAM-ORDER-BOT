"""Tests for BalanceService refund + status-only mark, incl. admin attribution."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import *  # noqa: F401,F403 — register all models
from src.database.models.base import Base
from src.database.models.bot_user import BotUser
from src.database.models.order import Order
from src.database.models.balance_transaction import BalanceTransaction
from src.database.models.enums import OrderStatus, BalanceTxKind
from src.database.services.balance_service import BalanceService


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _seed(session, status=OrderStatus.PAID, balance=0):
    user = BotUser(id="u1", telegram_user_id=555, username="bob", balance=balance)
    order = Order(id="ord1", user_id=555, status=status, total_amount=100000)
    session.add_all([user, order])
    session.commit()
    return user, order


def test_refund_order_credits_balance_and_sets_admin_id(session):
    user, _ = _seed(session, balance=20000)
    svc = BalanceService(session)
    ok, reason = svc.refund_order("ord1", 50000, admin_id="admin_1")
    assert (ok, reason) == (True, "ok")
    session.refresh(user)
    assert user.balance == 70000
    tx = session.query(BalanceTransaction).filter_by(reference_id="ord1").one()
    assert tx.kind == BalanceTxKind.REFUND
    assert tx.admin_id == "admin_1"
    assert "admin_1" in (tx.reason or "")
    assert session.query(Order).get("ord1").status == OrderStatus.REFUNDED


def test_refund_order_bot_path_unchanged(session):
    user, _ = _seed(session)
    svc = BalanceService(session)
    ok, reason = svc.refund_order("ord1", 10000, 999)  # positional telegram_admin_id
    assert (ok, reason) == (True, "ok")
    tx = session.query(BalanceTransaction).filter_by(reference_id="ord1").one()
    assert tx.admin_id is None
    assert "tg:999" in (tx.reason or "")


def test_mark_order_refunded_status_only(session):
    user, _ = _seed(session, balance=5000)
    svc = BalanceService(session)
    ok, reason = svc.mark_order_refunded("ord1")
    assert (ok, reason) == (True, "ok")
    session.refresh(user)
    assert user.balance == 5000  # untouched
    assert session.query(BalanceTransaction).count() == 0  # no audit row
    order = session.query(Order).get("ord1")
    assert order.status == OrderStatus.REFUNDED
    assert order.refunded_at is not None


def test_mark_order_refunded_idempotent(session):
    _seed(session)
    svc = BalanceService(session)
    assert svc.mark_order_refunded("ord1") == (True, "ok")
    assert svc.mark_order_refunded("ord1") == (False, "ineligible")


def test_mark_order_refunded_not_found(session):
    svc = BalanceService(session)
    assert svc.mark_order_refunded("missing") == (False, "not_found")


def test_mark_order_refunded_ineligible_status(session):
    _seed(session, status=OrderStatus.PENDING)
    svc = BalanceService(session)
    assert svc.mark_order_refunded("ord1") == (False, "ineligible")
