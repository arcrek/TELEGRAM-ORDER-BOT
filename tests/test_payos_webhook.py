"""
Tests for PayOS webhook endpoint.
"""

import atexit
import contextlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.dashboard.auth import get_db
from src.dashboard.main import app
from src.database.models import Order
from src.database.models.base import Base
from src.database.models.enums import OrderStatus
from src.payos.signature import create_hmac_sha256_hex

# Create test database file (shared across tests)
with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as test_db_file:
    test_db_path = test_db_file.name


def cleanup_test_db():
    with contextlib.suppress(Exception):
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)


atexit.register(cleanup_test_db)


test_engine = create_engine(
    f"sqlite:///{test_db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
Base.metadata.create_all(test_engine)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(monkeypatch):
    # Ensure checksum key is configured for signature verification
    monkeypatch.setenv("PAYOS_CHECKSUM_KEY", "test_checksum_key")

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    # Restore only the one key we changed, not all overrides
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture(autouse=True, scope="function")
def setup_database():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield


def test_payos_webhook_success_calls_processor(client, monkeypatch):
    # Arrange: create an order with payos_order_code
    session: Session = TestSession()
    order = Order(
        id="order_abc",
        user_id=123,
        status=OrderStatus.PENDING,
        total_amount=3000,
        payment_provider="payos",
        payos_order_code=123,
    )
    session.add(order)
    session.commit()
    session.close()

    calls = {}

    class FakeProcessor:
        bot = None
        supplier_bot = None

        def process_payment_success(self, order_id: str, transaction_id: str, amount: int, request_loop=None) -> bool:
            calls["order_id"] = order_id
            calls["transaction_id"] = transaction_id
            calls["amount"] = amount
            return True

    import src.dashboard.routers.payos_webhook as payos_webhook_module

    monkeypatch.setattr(payos_webhook_module, "get_ipn_processor", lambda: FakeProcessor())

    data = {
        "orderCode": 123,
        "amount": 3000,
        "description": "BotOrder",
        "accountNumber": "12345678",
        "reference": "REF123",
        "transactionDateTime": "2026-01-28 00:00:00",
        "currency": "VND",
        "paymentLinkId": "pl_1",
        "code": "00",
        "desc": "Thành công",
        "counterAccountBankId": "",
        "counterAccountBankName": "",
        "counterAccountName": "",
        "counterAccountNumber": "",
        "virtualAccountName": "",
        "virtualAccountNumber": "",
    }
    signature = create_hmac_sha256_hex(data, "test_checksum_key")

    payload = {"success": True, "data": data, "signature": signature}

    # Act
    resp = client.post("/api/payos/webhook", json=payload)

    # Assert
    assert resp.status_code == 200
    assert calls["order_id"] == "order_abc"
    assert calls["transaction_id"] == "REF123"
    assert calls["amount"] == 3000


def test_payos_webhook_invalid_signature_skips_processing(client, monkeypatch):
    session: Session = TestSession()
    order = Order(
        id="order_abc",
        user_id=123,
        status=OrderStatus.PENDING,
        total_amount=3000,
        payment_provider="payos",
        payos_order_code=123,
    )
    session.add(order)
    session.commit()
    session.close()

    called = {"hit": False}

    class FakeProcessor:
        bot = None
        supplier_bot = None

        def process_payment_success(self, order_id: str, transaction_id: str, amount: int) -> bool:
            called["hit"] = True
            return True

    import src.dashboard.routers.payos_webhook as payos_webhook_module

    monkeypatch.setattr(payos_webhook_module, "get_ipn_processor", lambda: FakeProcessor())

    payload = {
        "success": True,
        "data": {"orderCode": 123, "amount": 3000, "code": "00"},
        "signature": "bad_signature",
    }
    resp = client.post("/api/payos/webhook", json=payload)
    assert resp.status_code == 200
    assert called["hit"] is False
