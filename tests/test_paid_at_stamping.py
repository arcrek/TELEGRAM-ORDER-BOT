from src.database.connection import create_engine_instance
from src.database.models.base import Base
from src.database.models.order import Order
from src.database.models.bot_user import BotUser
from src.database.models.enums import OrderStatus
from src.database.services.order_service import OrderService
from src.database.services.balance_service import BalanceService
from sqlalchemy.orm import sessionmaker

# Import all models so Base.metadata is fully populated before create_all.
import src.database.models  # noqa: F401


def _session():
    engine = create_engine_instance("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_update_status_paid_stamps_paid_at_once():
    s = _session()
    s.add(Order(id="O1", user_id=1, total_amount=1000, status=OrderStatus.PENDING))
    s.commit()
    svc = OrderService(s)

    svc.update_order_status("O1", OrderStatus.PAID)
    first = s.get(Order, "O1").paid_at
    assert first is not None

    # A later status change must NOT re-stamp paid_at.
    svc.update_order_status("O1", OrderStatus.DELIVERED)
    assert s.get(Order, "O1").paid_at == first


def test_non_paid_status_does_not_stamp():
    s = _session()
    s.add(Order(id="O2", user_id=1, total_amount=1000, status=OrderStatus.PENDING))
    s.commit()
    svc = OrderService(s)
    svc.update_order_status("O2", OrderStatus.CANCELLED)
    assert s.get(Order, "O2").paid_at is None


def test_balance_path_stamps_paid_at():
    """Balance payment path (BalanceService.pay_order_with_balance) must stamp paid_at."""
    s = _session()

    # Insert a BotUser with enough balance to cover the order.
    user = BotUser(
        telegram_user_id=200001,
        balance=50_000,
    )
    s.add(user)
    s.commit()

    # Insert a PENDING Order belonging to this user.
    order = Order(
        id="O3",
        user_id=user.telegram_user_id,
        total_amount=10_000,
        status=OrderStatus.PENDING,
    )
    s.add(order)
    s.commit()

    svc = BalanceService(s)
    success, reason = svc.pay_order_with_balance("O3", user)

    assert success is True, f"Expected success but got ({success!r}, {reason!r})"
    assert reason == "ok"

    # Reload the order from the DB and check paid_at was stamped.
    s.expire_all()
    paid_order = s.get(Order, "O3")
    assert paid_order.paid_at is not None, (
        "paid_at must be set after balance payment — "
        "check that pay_order_with_balance sets paid_at=func.now()"
    )
