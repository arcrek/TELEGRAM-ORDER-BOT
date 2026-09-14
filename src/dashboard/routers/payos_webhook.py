"""
PayOS webhook router.

Receives payment notifications from PayOS and triggers order fulfillment.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db
from src.database.services.order_service import OrderService
from src.database.services.topup_service import TopupService
from src.ipn import get_ipn_processor
from src.payos.signature import verify_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def payos_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    PayOS webhook endpoint.

    PayOS expects a 2XX response to confirm delivery. We respond quickly and
    log/skip invalid signatures to avoid retry storms.
    """
    payload = await request.json()
    signature = payload.get("signature", "")
    data = payload.get("data") or {}

    checksum_key = os.getenv("PAYOS_CHECKSUM_KEY", "")
    if not checksum_key:
        logger.error("PAYOS_CHECKSUM_KEY is not configured; cannot verify webhook")
        return {"success": True}

    if not isinstance(data, dict):
        logger.error("Invalid PayOS webhook payload: data is not an object")
        return {"success": True}

    is_valid = verify_webhook_signature(data=data, signature=signature, checksum_key=checksum_key)
    if not is_valid:
        logger.error("Invalid PayOS webhook signature; skipping processing")
        return {"success": True}

    order_code = data.get("orderCode")
    amount = data.get("amount")
    result_code = data.get("code")
    success = payload.get("success", False)

    # PayOS uses code "00" for success
    if not (success and str(result_code) == "00"):
        logger.info(f"PayOS webhook non-success: orderCode={order_code}, code={result_code}, success={success}")
        return {"success": True}

    try:
        order_code_int = int(order_code)
    except (TypeError, ValueError):
        logger.error(f"Invalid orderCode in PayOS webhook: {order_code!r}")
        return {"success": True}

    order = OrderService(db).get_order_by_payos_code(order_code_int)
    if order:
        target_id = order.id
    else:
        topup = TopupService(db).get_by_payos_code(order_code_int)
        if not topup:
            logger.error(f"No Order or TopupOrder found for PayOS orderCode={order_code_int}")
            return {"success": True}
        target_id = topup.id

    try:
        amount_int = int(amount)
    except (TypeError, ValueError):
        logger.error(f"Invalid amount in PayOS webhook: {amount!r}")
        return {"success": True}

    # Use reference (bank ref) as transaction id, fallback to paymentLinkId
    transaction_id = str(data.get("reference") or data.get("paymentLinkId") or f"payos_{order_code_int}")

    logger.info(f"Processing PayOS webhook for target_id={target_id}, orderCode={order_code_int}, amount={amount_int}")

    processor = get_ipn_processor()
    logger.info(f"IPN processor created. Bot available: {processor.bot is not None}, Supplier bot available: {processor.supplier_bot is not None}")

    # Run sync processor in executor and pass the running loop so Telegram calls
    # are scheduled on it instead of creating a second loop (avoids "Event loop is closed")
    loop = asyncio.get_running_loop()
    processed = await loop.run_in_executor(
        None,
        lambda: processor.process_payment_success(
            order_id=target_id,
            transaction_id=transaction_id,
            amount=amount_int,
            request_loop=loop,
        ),
    )

    if processed:
        logger.info(f"✓ PayOS webhook processed successfully for target_id={target_id}, orderCode={order_code_int}")
    else:
        logger.error(f"✗ PayOS webhook processing FAILED for target_id={target_id}, orderCode={order_code_int}")
    
    return {"success": True}

