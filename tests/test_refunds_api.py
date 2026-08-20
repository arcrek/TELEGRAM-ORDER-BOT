"""Tests for the /api/refunds router."""
import atexit
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.dashboard.auth import create_access_token, get_db, get_password_hash
from src.dashboard.main import app
from src.database.models import *
from src.database.models.admin import Admin, AdminRole
from src.database.models.base import Base
from src.database.models.bot_user import BotUser
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.models.order import Order
from src.database.models.order_item import OrderItem
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation

with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as _f:
    _path = _f.name
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
    db.add(admin)
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(data={'sub': 'adm'})}"}


@pytest.fixture
def seeded(db: Session):
    user = BotUser(id="u1", telegram_user_id=777, username="alice",
                   first_name="Alice", balance=0)
    prod = Product(id="p1", name="Netflix", description="", delivery_type=DeliveryType.PRE_UPLOADED, is_active=True)
    var = ProductVariation(id="v1", product_id="p1", name="1 tháng", price=100000, stock=5, is_active=True)
    paid = Order(id="ordP", user_id=777, status=OrderStatus.PAID, total_amount=100000)
    pending = Order(id="ordX", user_id=777, status=OrderStatus.PENDING, total_amount=50000)
    db.add_all([user, prod, var, paid, pending])
    db.commit()
    db.add(OrderItem(id="oi1", order_id="ordP", product_id="p1", variation_id="v1",
                     quantity=1, unit_price=100000, subtotal=100000))
    db.commit()
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


def test_preview_recomputes_server_side(client, headers, seeded, db):
    # Make the paid order 15 days old against a 30-day duration → ~half refund.
    from datetime import datetime, timedelta
    o = db.get(Order, "ordP")
    o.created_at = datetime.utcnow() - timedelta(days=15)
    db.commit()

    r = client.post("/api/refunds/preview", headers=headers,
                    json={"items": [{"order_id": "ordP", "days": 0, "months": 1, "years": 0}]})
    assert r.status_code == 200
    body = r.json()
    row = body["rows"][0]
    assert row["duration_days"] == 30
    assert row["elapsed"] == 15
    assert row["refund_amount"] == 50000
    assert body["total_refund"] == 50000


def test_preview_ineligible_is_zero(client, headers, seeded):
    r = client.post("/api/refunds/preview", headers=headers,
                    json={"items": [{"order_id": "ordX", "days": 30}]})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["eligible"] is False
    assert row["refund_amount"] == 0


def test_preview_unknown_order(client, headers, seeded):
    r = client.post("/api/refunds/preview", headers=headers,
                    json={"items": [{"order_id": "ghost", "days": 30}]})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["refund_amount"] == 0
    assert row["eligible"] is False


def test_confirm_credit_moves_money(client, headers, seeded, db):
    from datetime import datetime, timedelta
    o = db.get(Order, "ordP")
    o.created_at = datetime.utcnow() - timedelta(days=15)
    db.commit()

    r = client.post("/api/refunds/confirm", headers=headers, json={"items": [
        {"order_id": "ordP", "days": 0, "months": 1, "years": 0, "mode": "credit"}
    ]})
    assert r.status_code == 200
    res = r.json()["results"][0]
    assert res["success"] is True
    assert res["refund_amount"] == 50000
    assert res["new_balance"] == 50000
    assert db.get(Order, "ordP").status == OrderStatus.REFUNDED
    bt = db.query(BotUser).filter_by(telegram_user_id=777).one()
    assert bt.balance == 50000


def test_confirm_status_only(client, headers, seeded, db):
    r = client.post("/api/refunds/confirm", headers=headers, json={"items": [
        {"order_id": "ordP", "mode": "status"}
    ]})
    assert r.status_code == 200
    assert r.json()["results"][0]["success"] is True
    assert db.get(Order, "ordP").status == OrderStatus.REFUNDED
    assert db.query(BotUser).filter_by(telegram_user_id=777).one().balance == 0


def test_confirm_mixed_eligibility(client, headers, seeded):
    r = client.post("/api/refunds/confirm", headers=headers, json={"items": [
        {"order_id": "ordX", "days": 30, "mode": "credit"},  # pending → ineligible
        {"order_id": "ghost", "mode": "status"},             # missing
    ]})
    res = {x["order_id"]: x for x in r.json()["results"]}
    assert res["ordX"]["success"] is False
    assert res["ghost"]["success"] is False
    assert res["ghost"]["reason"] == "not_found"


def test_confirm_zero_refund_skipped(client, headers, seeded, db):
    from datetime import datetime, timedelta
    o = db.get(Order, "ordP")
    o.created_at = datetime.utcnow() - timedelta(days=400)  # expired
    db.commit()
    r = client.post("/api/refunds/confirm", headers=headers, json={"items": [
        {"order_id": "ordP", "days": 30, "mode": "credit"}
    ]})
    res = r.json()["results"][0]
    assert res["success"] is False
    assert res["reason"] == "no_refund"
    assert db.get(Order, "ordP").status == OrderStatus.PAID  # unchanged


def test_confirm_requires_admin_role(client, seeded):
    r = client.post("/api/refunds/confirm", json={"items": [
        {"order_id": "ordP", "mode": "status"}
    ]})
    assert r.status_code == 401


def test_confirm_forbidden_for_viewer(client, seeded, db: Session):
    viewer = Admin(id="viewer_1", username="vwr", email="v@x.com",
                   password_hash=get_password_hash("pw"), full_name="V",
                   role=AdminRole.VIEWER, is_active=True)
    db.add(viewer)
    db.commit()
    viewer_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'vwr'})}"}
    r = client.post("/api/refunds/confirm", headers=viewer_headers,
                    json={"items": [{"order_id": "ordP", "mode": "status"}]})
    assert r.status_code == 403
