"""
PayOS Merchant API client (minimal).

API base URL (prod): https://api-merchant.payos.vn
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from src.payos.signature import create_payment_request_signature


@dataclass(frozen=True)
class PayOSCredentials:
    client_id: str
    api_key: str
    checksum_key: str
    partner_code: str = ""


class PayOSClient:
    def __init__(self, *, base_url: str, credentials: PayOSCredentials, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> Dict[str, str]:
        headers = {
            "x-client-id": self.credentials.client_id,
            "x-api-key": self.credentials.api_key,
            "Content-Type": "application/json",
        }
        if self.credentials.partner_code:
            headers["x-partner-code"] = self.credentials.partner_code
        return headers

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

