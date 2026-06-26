"""Tests for the /api/refunds router."""
import tempfile, os, atexit
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.dashboard.main import app
from src.dashboard.auth import get_password_hash, create_access_token, get_db
from src.database.models import *  # noqa: F401,F403
from src.database.models.base import Base
from src.database.models.admin import Admin, AdminRole
from src.database.models.bot_user import BotUser
from src.database.models.order import Order
from src.database.models.order_item import OrderItem
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.models.enums import OrderStatus, DeliveryType

_f = tempfile.NamedTemporaryFile(delete=False, suffix=".db"); _path = _f.name; _f.close()
atexit.register(lambda: os.path.exists(_path) and os.unlink(_path))
engine = create_engine(f"sqlite:///{_path}", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)


def override_get_db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    s = TestSession()
    yield s
    s.close()


@pytest.fixture
def headers(db: Session):
    admin = Admin(id="admin_1", username="adm", email="a@x.com",
                  password_hash=get_password_hash("pw"), full_name="A",
                  role=AdminRole.ADMIN, is_active=True)
    db.add(admin); db.commit()
    return {"Authorization": f"Bearer {create_access_token(data={'sub': 'adm'})}"}


@pytest.fixture
def seeded(db: Session):
    user = BotUser(id="u1", telegram_user_id=777, username="alice",
                   first_name="Alice", balance=0)
    prod = Product(id="p1", name="Netflix", description="", delivery_type=DeliveryType.PRE_UPLOADED, is_active=True)
    var = ProductVariation(id="v1", product_id="p1", name="1 tháng", price=100000, stock=5, is_active=True)
    paid = Order(id="ordP", user_id=777, status=OrderStatus.PAID, total_amount=100000)
    pending = Order(id="ordX", user_id=777, status=OrderStatus.PENDING, total_amount=50000)
    db.add_all([user, prod, var, paid, pending]); db.commit()
    db.add(OrderItem(id="oi1", order_id="ordP", product_id="p1", variation_id="v1",
                     quantity=1, unit_price=100000, subtotal=100000)); db.commit()
    return user


def test_orders_by_telegram_id(client, headers, seeded):
    r = client.get("/api/refunds/orders", params={"search": "777"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["telegram_user_id"] == 777
    assert body["user"]["username"] == "alice"
    ids = {o["id"]: o for o in body["orders"]}
    assert ids["ordP"]["eligible"] is True
    assert ids["ordX"]["eligible"] is False
    assert ids["ordX"]["ineligible_reason"]  # non-empty
    assert ids["ordP"]["items"][0]["product"] == "Netflix"
    assert ids["ordP"]["items"][0]["variation"] == "1 tháng"


def test_orders_by_username(client, headers, seeded):
    r = client.get("/api/refunds/orders", params={"search": "@alice"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["user"]["telegram_user_id"] == 777


def test_orders_user_not_found(client, headers, seeded):
    r = client.get("/api/refunds/orders", params={"search": "nope"}, headers=headers)
    assert r.status_code == 404


def test_orders_requires_auth(client, seeded):
    r = client.get("/api/refunds/orders", params={"search": "777"})
    assert r.status_code == 401
