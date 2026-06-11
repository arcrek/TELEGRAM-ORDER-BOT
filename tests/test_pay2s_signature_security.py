"""
Security tests for Pay2S signature verification.
"""
import time

from src.pay2s.signature import generate_ipn_signature, verify_ipn_signature

SECRET_KEY = "test-secret-key"
ACCESS_KEY = "test-access-key"


def _make_ipn_data() -> dict:
    data = {
        "partnerCode": "TESTPARTNER",
        "orderId": "ORD123",
        "requestId": "REQ123",
        "amount": 50000,
        "orderInfo": "Test order",
        "orderType": "Pay2S_wallet",
        "transId": 999111,
        "resultCode": 0,
        "message": "Giao dich thanh cong.",
        "payType": "qr",
        "accessKey": ACCESS_KEY,
        "extraData": "",
        "responseTime": int(time.time() * 1000),
    }
    data["signature"] = generate_ipn_signature(
        access_key=data["accessKey"],
        amount=data["amount"],
        extra_data=data["extraData"],
        message=data["message"],
        order_id=data["orderId"],
        order_info=data["orderInfo"],
        order_type=data["orderType"],
        partner_code=data["partnerCode"],
        pay_type=data["payType"],
        request_id=data["requestId"],
        response_time=str(data["responseTime"]),
        result_code=str(data["resultCode"]),
        trans_id=str(data["transId"]),
        secret_key=SECRET_KEY,
    )
    return data


def test_valid_signature_accepted():
    data = _make_ipn_data()
    is_valid, _, _ = verify_ipn_signature(data, SECRET_KEY)
    assert is_valid


def test_tampered_amount_rejected():
    data = _make_ipn_data()
    data["amount"] = 1  # attacker changes amount after signing
    is_valid, _, _ = verify_ipn_signature(data, SECRET_KEY)
    assert not is_valid


def test_forged_signature_rejected():
    data = _make_ipn_data()
    data["signature"] = "deadbeef" * 8
    is_valid, _, _ = verify_ipn_signature(data, SECRET_KEY)
    assert not is_valid


def test_missing_signature_rejected():
    data = _make_ipn_data()
    del data["signature"]
    is_valid, _, _ = verify_ipn_signature(data, SECRET_KEY)
    assert not is_valid
