from src.database.connection import create_engine_instance
from src.database.models.base import Base
from src.database.models.order import Order
from src.database.models.enums import OrderStatus
from src.database.services.order_service import OrderService
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine_instance("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


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
