"""
PayOS Merchant API client (minimal).

API base URL (prod): https://api-merchant.payos.vn
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from src.payos.signature import create_payment_request_signature

PAYOS_API_BASE_URL = "https://api-merchant.payos.vn"


@dataclass(frozen=True)
class PayOSCredentials:
    client_id: str
    api_key: str
    checksum_key: str


def build_payos_client() -> "PayOSClient":
    values = {
        "PAYOS_CLIENT_ID": os.getenv("PAYOS_CLIENT_ID", "").strip(),
        "PAYOS_API_KEY": os.getenv("PAYOS_API_KEY", "").strip(),
        "PAYOS_CHECKSUM_KEY": os.getenv("PAYOS_CHECKSUM_KEY", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"Missing PayOS configuration: {', '.join(missing)}")
    return PayOSClient(
        base_url=PAYOS_API_BASE_URL,
        credentials=PayOSCredentials(
            client_id=values["PAYOS_CLIENT_ID"],
            api_key=values["PAYOS_API_KEY"],
            checksum_key=values["PAYOS_CHECKSUM_KEY"],
        ),
    )


class PayOSClient:
    def __init__(self, *, base_url: str, credentials: PayOSCredentials, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> Dict[str, str]:
        return {
            "x-client-id": self.credentials.client_id,
            "x-api-key": self.credentials.api_key,
            "Content-Type": "application/json",
        }

    def create_payment_link(
        self,
        *,
        order_code: int,
        amount: int,
        description: str,
        return_url: str,
        cancel_url: str,
        expired_at: Optional[int] = None,
        buyer_name: Optional[str] = None,
        buyer_email: Optional[str] = None,
        buyer_phone: Optional[str] = None,
        buyer_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create PayOS payment link.

        Returns full JSON response from PayOS.
        """
        signature = create_payment_request_signature(
            amount=amount,
            cancel_url=cancel_url,
            description=description,
            order_code=order_code,
            return_url=return_url,
            checksum_key=self.credentials.checksum_key,
        )

        payload: Dict[str, Any] = {
            "orderCode": int(order_code),
            "amount": int(amount),
            "description": str(description),
            "cancelUrl": str(cancel_url),
            "returnUrl": str(return_url),
            "signature": signature,
        }

        if expired_at is not None:
            payload["expiredAt"] = int(expired_at)
        if buyer_name:
            payload["buyerName"] = buyer_name
        if buyer_email:
            payload["buyerEmail"] = buyer_email
        if buyer_phone:
            payload["buyerPhone"] = buyer_phone
        if buyer_address:
            payload["buyerAddress"] = buyer_address

        url = f"{self.base_url}/v2/payment-requests"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "00":
            raise ValueError(f"PayOS create_payment_link failed: {data.get('code')} - {data.get('desc')}")
        return data

    def cancel_payment_link(self, *, payment_link_id: str, cancellation_reason: str = "cancelled") -> Dict[str, Any]:
        url = f"{self.base_url}/v2/payment-requests/{payment_link_id}/cancel"
        resp = requests.post(
            url,
            headers=self._headers(),
            json={"cancellationReason": cancellation_reason},
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "00":
            raise ValueError(f"PayOS cancel_payment_link failed: {data.get('code')} - {data.get('desc')}")
        return data
