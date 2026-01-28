"""
PayOS Signature utilities.

Docs:
- Create payment link signature: HMAC_SHA256 over sorted query string of
  amount, cancelUrl, description, orderCode, returnUrl using checksumKey.
- Webhook signature: HMAC_SHA256 over sorted query string of payload["data"].
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict


def _sort_obj_by_key(obj: Dict[str, Any]) -> Dict[str, Any]:
    return dict(sorted(obj.items(), key=lambda kv: kv[0]))


def _normalize_value(value: Any) -> str:
    """
    Normalize values according to PayOS signature docs/examples:
    - null/undefined/"null"/"undefined" -> ""
    - list -> JSON string of list (with any dict elements sorted by key)
    - bool/int/float -> str(value)
    - dict -> JSON string of sorted dict
    - other -> str(value)
    """
    if value in (None, "null", "NULL", "undefined", "UNDEFINED"):
        return ""

    if isinstance(value, (bool, int, float)):
        return str(value)

    if isinstance(value, list):
        normalized_list = []
        for item in value:
            if isinstance(item, dict):
                normalized_list.append(_sort_obj_by_key(item))
            else:
                normalized_list.append(item)
        return json.dumps(normalized_list, ensure_ascii=False, separators=(",", ":"))

    if isinstance(value, dict):
        return json.dumps(_sort_obj_by_key(value), ensure_ascii=False, separators=(",", ":"))

    return str(value)


def to_sorted_query_string(data: Dict[str, Any]) -> str:
    sorted_data = _sort_obj_by_key(data)
    parts: list[str] = []
    for key, value in sorted_data.items():
        parts.append(f"{key}={_normalize_value(value)}")
    return "&".join(parts)


def create_hmac_sha256_hex(data: Dict[str, Any], checksum_key: str) -> str:
    raw = to_sorted_query_string(data)
    return hmac.new(
        checksum_key.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_payment_request_signature(
    *,
    amount: int,
    cancel_url: str,
    description: str,
    order_code: int,
    return_url: str,
    checksum_key: str,
) -> str:
    data = {
        "amount": amount,
        "cancelUrl": cancel_url,
        "description": description,
        "orderCode": order_code,
        "returnUrl": return_url,
    }
    return create_hmac_sha256_hex(data, checksum_key)


def verify_webhook_signature(*, data: Dict[str, Any], signature: str, checksum_key: str) -> bool:
    expected = create_hmac_sha256_hex(data, checksum_key)
    return hmac.compare_digest(expected.lower(), (signature or "").lower())

