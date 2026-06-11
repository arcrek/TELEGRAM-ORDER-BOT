"""
The Pay2S IPN endpoint must reject requests with invalid signatures
and must NOT process the transaction for them.
"""
import time
from unittest.mock import MagicMock

from src.pay2s.ipn import create_ipn_app
from src.pay2s.signature import generate_ipn_signature

SECRET_KEY = "test-secret-key"
ACCESS_KEY = "test-access-key"


def _ipn_payload(signed: bool) -> dict:
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
    if signed:
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
    else:
        data["signature"] = "forged-signature"
    return data


def _client_and_mock():
    process_mock = MagicMock(return_value=True)
    app = create_ipn_app(SECRET_KEY, process_transaction_callback=process_mock)
    app.config["TESTING"] = True
    return app.test_client(), process_mock


def test_invalid_signature_is_rejected_and_not_processed():
    client, process_mock = _client_and_mock()
    resp = client.post("/ipn", json=_ipn_payload(signed=False))
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
    process_mock.assert_not_called()


def test_valid_signature_is_processed():
    client, process_mock = _client_and_mock()
    resp = client.post("/ipn", json=_ipn_payload(signed=True))
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    process_mock.assert_called_once()
