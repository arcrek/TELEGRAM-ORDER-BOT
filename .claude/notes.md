# Technical Notes & Risks

## Critical Issues

### 1. Global Mutable State in IPN Processor
**File:** `src/ipn/processor.py` (lines 711–734)  
**Risk:** HIGH

`_global_bot` and `_global_supplier_bot` are module-level variables mutated at runtime. In a multi-worker gunicorn deployment, each worker has its own copy (fine), but the bot is only set in the `bot` container — not in the `api` container. The API container falls back to creating a fresh `Bot()` from env vars on every IPN call. This works but creates a new HTTP session per invocation.

**Suggestion:** Pass bot instances through the call chain instead of using globals, or initialize once at startup.

---

### 2. Session Not Returned to Pool After IPN Processing
**File:** `src/ipn/processor.py`, `process_payment_success` (line 283)

The method creates its own session via `self.session_factory()` and closes it in `finally`. However, the sub-methods (`_handle_pre_uploaded_delivery`, `_handle_upgrade_delivery`) receive this same session and also call `session.commit()` internally. If a sub-method raises after `session.commit()` has already been called once, `session.rollback()` in the outer except may be a no-op, leaving the DB in a partially committed state.

**Suggestion:** Use a single transaction scope with explicit savepoints, or restructure to commit only once at the end.

---

### 3. In-Memory Bot State (No Persistence)
**File:** `src/bot/states/state_manager.py`

User session state is stored in a plain dict in memory. Restarting the bot (crash, redeploy) discards all in-progress flows (custom quantity input, pending orders, etc.). Users mid-purchase will lose their state.

**Suggestion:** Store state in Redis or the database for resilience.

---

### 4. `run_async` Complexity and Edge Cases
**File:** `src/ipn/processor.py` (lines 54–88)

The `run_async()` helper has three distinct code paths to handle different asyncio contexts. The "loop is running but we're on the loop thread" path creates a new event loop in a `ThreadPoolExecutor`. This can cause issues with httpx connection pooling (used by python-telegram-bot) if called frequently. This code is complex and hard to test.

**Suggestion:** Separate sync and async delivery paths cleanly. If `process_payment_success` is always called from a thread, use `asyncio.run()` exclusively.

---

## Code Smells

### 5. Supplier Bot Code Left In (Disabled)
The supplier bot (`src/bot_supplier/`) is fully implemented but disabled everywhere via comments in `docker-compose.yml` and `src/dashboard/main.py`. This is dead code that adds maintenance overhead.

**Suggestion:** Either re-enable it or delete it and remove the `SupplierOrder`, `Supplier`, and `ProductSupplierAssignment` models.

---

### 6. Hardcoded English Error Messages in IPN Processor
**File:** `src/ipn/processor.py` (lines 258, 316, 399, 556)

While bot messages go through the i18n system, IPN error messages are hardcoded English strings sent directly to users:
```python
"⚠️ Order {order_id} partially delivered..."
"❌ Payment failed for order {order_id}..."
```
These bypass the translation layer.

---

### 7. `OrderStatusUpdate` Schema Accepts Any String
**File:** `src/dashboard/routers/orders.py`, line 17–19

```python
class OrderStatusUpdate(BaseModel):
    status: str  # Should be Enum(OrderStatus)
```
The API accepts invalid status strings and only fails at the DB level. Should use `OrderStatus` enum directly.

---

### 8. CORS Wildcard in Production
**File:** `src/dashboard/main.py`, line 35

```python
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
```
Default is `*` (allow all). In production, `CORS_ORIGINS` must be set to the actual frontend domain or this is a security risk.

---

### 9. JWT Secret Key Not Validated at Startup
**File:** `src/dashboard/auth.py`, line 20

```python
SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY")
```
If `DASHBOARD_SECRET_KEY` is not set, `SECRET_KEY` is `None`. The JWT library will either silently use `None` as key or fail at runtime on the first auth attempt. No validation at startup.

**Suggestion:** Add a startup check:
```python
if not SECRET_KEY:
    raise RuntimeError("DASHBOARD_SECRET_KEY env var is required")
```

---

## Performance Concerns

### 10. No Database Query Caching
Every `/products` command from Telegram triggers a full DB query. With many concurrent users, this will generate significant DB load. Consider adding a short-lived cache (Redis, or even an in-process TTL cache) for product listings.

### 11. APScheduler in Bot Process
`AutoCancelTask` runs inside the bot process using APScheduler's `BackgroundScheduler`. If the bot crashes, auto-cancellation also stops. In Docker, the bot restarts automatically, but there's a window where orders are not cancelled.

### 12. Delivery File Written to Disk Then Deleted
`_send_pre_uploaded_products` writes to `delivery_data/<order_id>.txt` and then deletes it after successful Telegram send. This adds disk I/O for every delivery. The content is already in memory — the file write is only for persistence in case the send fails. Consider making this explicit (e.g., keep the file only if send fails).

---

## Improvement Suggestions

| Area | Suggestion |
|------|-----------|
| State management | Move bot state to Redis/DB for persistence across restarts |
| IPN processor | Use a proper async task queue (Celery, ARQ) instead of `run_async` hacks |
| Config validation | Use Pydantic `BaseSettings` for env var validation at startup |
| CORS | Enforce `CORS_ORIGINS` in production; reject `*` in non-dev environments |
| Secret key | Validate `DASHBOARD_SECRET_KEY` at startup |
| Supplier code | Remove dead supplier code or re-enable it with tests |
| i18n for IPN errors | Route all user-facing IPN messages through the i18n system |
| Order status update | Use `OrderStatus` enum in `OrderStatusUpdate` schema |
| Connection pooling | Add monitoring for pool exhaustion (log `pool_timeout` events) |
| Delivery idempotency | The duplicate-delivery check (`status == DELIVERED`) is present but relies on race condition luck — consider a DB-level unique constraint on `payment_transaction_id` |

---

## Files Developers Must Read First

1. `src/database/connection.py` — session lifecycle
2. `src/database/models/enums.py` — enum values used everywhere
3. `src/ipn/processor.py` — the most critical and complex file
4. `src/bot/main.py` — handler registration order
5. `src/dashboard/auth.py` — JWT dependency chain
6. `CLAUDE.md` — project-level coding conventions
