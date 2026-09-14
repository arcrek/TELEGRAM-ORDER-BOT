# Phase 3: Architectural Boundaries & Operational Hygiene

**Status: Complete [x]**

## Overview
Restore strict service layer boundaries, eliminate plaintext secret logging, and resolve StateManager singleton fragmentation.

## Scope of Work

### 1. Service Layer Encapsulation in Webhook Router (`[HIGH-02]`)
- **Files:**
  - `src/dashboard/routers/payos_webhook.py`
  - `src/database/services/order_service.py`
  - `src/database/services/topup_service.py`
- **Actions:**
  - In `OrderService`: add `get_order_by_payos_code(order_code: int) -> Order | None`.
  - In `TopupService`: add `get_by_payos_code(order_code: int) -> TopupOrder | None`.
  - In `payos_webhook.py`: replace direct `db.query(Order)` and `db.query(TopupOrder)` with calls to `OrderService(db).get_order_by_payos_code(...)` and `TopupService(db).get_by_payos_code(...)`.
  - Enforce `AGENTS.md` mandate: "New handlers/routes must not query or mutate models directly."

### 2. Redact Plaintext Secrets in Delivery Logs (`[HIGH-03]`)
- **Files:**
  - `src/ipn/processor.py`
- **Actions:**
  - In lines 898-900:
    - Replace `logger.info(f"Product: {product}")` and `logger.info(f"Product data: {product_data}")` with safe metadata logging:
      ```python
      logger.info(f"Delivering product {product.get('id')} to user {user_id} (data_present={bool(product_data)})")
      ```
    - Ensure license keys, credentials, and customer secrets are never written to log handlers.

### 3. Eviction & TTL for In-Memory Order Locks (`[HIGH-04]`)
- **Files:**
  - `src/ipn/processor.py`
- **Actions:**
  - Add cleanup logic to `_order_locks`:
    - After processing an order inside `_process_payment_success_impl()`, remove the lock entry from `_order_locks` under `_order_locks_guard` once the critical section completes.
    - Prevent monotonic memory growth across long-running daemon lifecycles.

### 4. Unify `StateManager` into Shared Singleton (`[HIGH-05]`)
- **Files:**
  - `src/bot/states/state_manager.py`
  - `src/bot/handlers/balance.py`
  - `src/bot/handlers/callbacks.py`
  - `src/bot/handlers/commands.py`
  - `src/bot/handlers/upgrade_handler.py`
  - `src/database/services/auto_cancel_service.py`
  - `src/ipn/processor.py`
- **Actions:**
  - In `src/bot/states/state_manager.py`: export a module-level singleton `shared_state_manager = StateManager()` or apply singleton pattern in `__new__`.
  - Update all handlers and services to import and use the shared singleton instead of instantiating separate module-level dictionaries.

## Verification & Acceptance
- `payos_webhook.py` imports no SQLAlchemy models directly.
- Delivery execution produces clean logs without credentials.
- `_order_locks` size does not grow monotonically with each order.
- `state_manager` updates in one handler are reflected in other bot handlers.
