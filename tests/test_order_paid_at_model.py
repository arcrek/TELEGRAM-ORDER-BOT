from src.database.connection import create_engine_instance
from src.database.models.base import Base
from src.database.models.order import Order
from sqlalchemy.orm import sessionmaker


def test_order_has_nullable_paid_at():
    engine = create_engine_instance("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        o = Order(id="O1", user_id=1, total_amount=1000)
        s.add(o)
        s.commit()
        assert o.paid_at is None  # nullable, unset by default
