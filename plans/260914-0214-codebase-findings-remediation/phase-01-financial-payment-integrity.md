# Phase 1: Financial & Payment Integrity Fixes

**Status: Complete [x]**

## Overview
Remediate core financial loss and inventory corruption vulnerabilities in PayOS payment processing and digital fulfillment.

## Scope of Work

### 1. Late Topup Payment Recovery (`[CRIT-01]`)
- **Files:** `src/database/services/balance_service.py`, `src/ipn/processor.py`
- **Actions:**
  - Update `BalanceService.credit_topup(topup_id, transaction_id)`:
    - Check current status of `TopupOrder`.
    - If status is `PENDING`, transition atomically to `PAID` and credit balance.
    - If status is `CANCELLED`, allow atomic transition `CANCELLED -> PAID`, credit the user's wallet, record `BalanceTransaction(kind=TOPUP)`, and return `(True, "reactivated_cancelled")`.
    - If status is already `PAID`, return `(False, "already_processed")`.
  - Update `IPNOrderProcessor._process_topup_payment_impl()`:
    - Handle `reactivated_cancelled`: log an audit notice, credit the balance, notify user via Telegram of late topup recovery, and alert admin channel.

### 2. Zombie Order Resurrection Protection (`[CRIT-04]`)
- **Files:** `src/ipn/processor.py`
- **Actions:**
  - In `_process_payment_success_impl()`:
    - Add explicit guard before transitioning order status:
      ```python
      if order.status in (OrderStatus.CANCELLED, OrderStatus.REFUNDED):
          logger.error(
              f"Received payment for {order.status.value} order {order_id}. "
              f"Transaction: {transaction_id}, Amount: {amount}. Aborting fulfillment."
          )
          order.payment_transaction_id = transaction_id
          session.commit()
          # Alert admin for manual reconciliation / refund
          OrderNotificationService(session, self.bot).send_late_payment_alert(order, transaction_id, amount)
          return False
      ```
    - Ensure cancelled orders never transition to `PAID` or trigger stock fulfillment.

### 3. Re-entrant Digital Delivery (`[HIGH-01]`)
- **Files:** `src/database/services/pre_uploaded_service.py`
- **Actions:**
  - In `deliver_order(order_id)`:
    - Before querying for new items with `is_used = False`, check if items already exist with `used_by_order_id == order_id`.
    - If already delivered/marked (e.g. from an earlier attempt where Telegram transmission timed out), return the existing marked products directly.
    - Prevent consuming secondary stock rows on repeated delivery attempts.

### 4. Stock Reservation Cleanup on Order Refund (`[HIGH-06]`)
- **Files:** `src/database/services/balance_service.py`
- **Actions:**
  - In `refund_order(order_id)`:
    - Call `PreUploadedService(self.session).release_reservations_for_order(order_id)` to ensure any reserved items held by the refunded order are released back to available inventory.

## Verification & Acceptance
- Late topup webhook on auto-cancelled topup credits balance and records transaction.
- Webhook on cancelled product order does not deliver unreserved stock.
- Re-running delivery for an order does not increment consumed inventory.
