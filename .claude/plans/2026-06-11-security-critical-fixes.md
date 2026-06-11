# Security & Reliability Critical Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the payment-forgery hole in the Pay2S IPN handler and fix the eight other critical/high findings from the 2026-06-11 codebase review (timing-safe HMAC, secret/CORS validation, double-tap payment guard, concurrent-IPN fulfillment lock, asyncio.run in scheduler thread, role enforcement, CI).

**Architecture:** All fixes are surgical changes to existing modules — no new subsystems. Each task is independent, committed separately, and verified by a test written first (TDD). The bot is a single-process asyncio app; the IPN server is threaded Flask; the dashboard is FastAPI. Fixes respect those concurrency models.

**Tech Stack:** Python 3.11, FastAPI, Flask, python-telegram-bot ≥22, SQLAlchemy 2.0, APScheduler, pytest. Frontend untouched except CI.

**Conventions that apply to every task:**
- Run the project's tests with plain `pytest` from the repo root (`/home/arcrek/MTK_BOT_ORDER`).
- Commit after each task with the exact message given. Never combine tasks in one commit.
- Before writing a new test file, skim one existing test file in `tests/` that covers the same area (named in each task) and match its style (imports, fixtures, sync vs async).
- If a step's expected output differs from reality, STOP and report rather than improvising a different design.

---

## Task 0: Baseline

**Files:** none modified.

- [ ] **Step 0.1: Record the test baseline**

Run: `cd /home/arcrek/MTK_BOT_ORDER && pytest -q 2>&1 | tail -20`

Record the pass/fail count. If any tests already fail, write the list of failing test names into a scratch note — those failures are pre-existing and NOT your responsibility, but you must not add new ones. All later "run the full suite" steps compare against this baseline.

- [ ] **Step 0.2: Record the lint baseline**

Run: `cd /home/arcrek/MTK_BOT_ORDER && ruff check . 2>&1 | tail -5`

Record whether it is clean. This decides whether Task 9 includes a ruff step in CI.

---

## Task 1: Timing-safe Pay2S signature comparison

**Files:**
- Modify: `src/pay2s/signature.py:122`
- Test: `tests/test_pay2s_signature_security.py` (create)

Context: `src/pay2s/signature.py` already does `import hmac` at the top. `verify_ipn_signature(ipn_data, secret_key)` returns `(is_valid, partner_signature, debug_info)`. Line 122 currently reads `is_valid = received_signature == partner_signature`.

- [ ] **Step 1.1: Write the failing-then-passing test**

Create `tests/test_pay2s_signature_security.py`:

```python
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
```

- [ ] **Step 1.2: Run the new test — should already pass (behavioral baseline)**

Run: `pytest tests/test_pay2s_signature_security.py -v`
Expected: 4 PASSED. (The `==` comparison is functionally correct; the flaw is timing leakage, which a unit test can't observe. The test pins behavior so the next step can't regress it.)

- [ ] **Step 1.3: Make the comparison timing-safe**

In `src/pay2s/signature.py`, replace line 122:

```python
        # Verify signature
        is_valid = received_signature == partner_signature
```

with:

```python
        # Verify signature (timing-safe; received value is attacker-controlled)
        is_valid = hmac.compare_digest(str(received_signature), str(partner_signature))
```

- [ ] **Step 1.4: Run the tests again**

Run: `pytest tests/test_pay2s_signature_security.py tests/test_ipn.py -v`
Expected: all PASS.

- [ ] **Step 1.5: Commit**

```bash
git add src/pay2s/signature.py tests/test_pay2s_signature_security.py
git commit -m "fix(pay2s): use timing-safe comparison for IPN signature verification"
```

---

## Task 2: Pay2S IPN handler must REJECT invalid signatures

**Files:**
- Modify: `src/pay2s/ipn.py:117-123`
- Test: `tests/test_pay2s_ipn_rejection.py` (create)

Context: `create_ipn_app(secret_key, process_transaction_callback=None)` in `src/pay2s/ipn.py` builds a Flask app with a POST `/ipn` route. Today, when `verify_ipn_signature` returns invalid, it merely logs (`ipn.py:117-123` — the rejection `return` is commented out) and still calls `process_func(ipn_data)`. This lets anyone forge "payment succeeded" callbacks. **This is the single most important fix in the plan.**

- [ ] **Step 2.1: Write the failing test**

Create `tests/test_pay2s_ipn_rejection.py`:

```python
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
```

- [ ] **Step 2.2: Run it to confirm the security failure**

Run: `pytest tests/test_pay2s_ipn_rejection.py -v`
Expected: `test_invalid_signature_is_rejected_and_not_processed` FAILS (handler returns 200 and the mock WAS called). `test_valid_signature_is_processed` PASSES.

- [ ] **Step 2.3: Fix the handler**

In `src/pay2s/ipn.py`, replace lines 117–123:

```python
            if not is_valid:
                logger.error(f"Invalid signature!")
                logger.error(f"Raw Hash used: {debug_info.get('rawHash')}")
                # Still return success to avoid Pay2S retrying (log the issue for debugging)
                logger.warning("Returning success despite invalid signature to prevent retries")
                # Uncomment below to reject invalid signatures:
                # return jsonify({"success": False, "message": "Invalid signature"}), 400
```

with:

```python
            if not is_valid:
                logger.error("Invalid IPN signature — rejecting request")
                logger.error(f"Raw Hash used: {debug_info.get('rawHash')}")
                return jsonify({"success": False, "message": "Invalid signature"}), 400
```

- [ ] **Step 2.4: Run the tests**

Run: `pytest tests/test_pay2s_ipn_rejection.py tests/test_pay2s_signature_security.py -v`
Expected: all PASS.

- [ ] **Step 2.5: Commit**

```bash
git add src/pay2s/ipn.py tests/test_pay2s_ipn_rejection.py
git commit -m "fix(pay2s): reject IPN requests with invalid signatures instead of processing them"
```

---

## Task 3: Fail fast with a clear error when DASHBOARD_SECRET_KEY is missing

**Files:**
- Modify: `src/dashboard/auth.py` (lines 20, 120, 148)
- Test: `tests/test_dashboard_auth.py` (append one test)

Context: `auth.py:20` reads `SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY")` with no check. With `None`, jose raises an opaque error at runtime. The check must be **lazy** (at first use, not import) because tests set the env var at runtime before exercising auth (see `tests/test_bot_ui_settings_api.py:51`). Read the top of `tests/test_dashboard_auth.py` first to match its fixture/import style.

- [ ] **Step 3.1: Write the failing test**

Append to `tests/test_dashboard_auth.py`:

```python
def test_create_access_token_requires_secret_key(monkeypatch):
    """A missing DASHBOARD_SECRET_KEY must produce a clear error, not a jose traceback."""
    import pytest
    from src.dashboard import auth as dashboard_auth

    monkeypatch.delenv("DASHBOARD_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DASHBOARD_SECRET_KEY"):
        dashboard_auth.create_access_token({"sub": "admin"})


def test_create_access_token_works_when_secret_set(monkeypatch):
    """With the env var present, token creation succeeds."""
    from src.dashboard import auth as dashboard_auth

    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "unit-test-secret")
    token = dashboard_auth.create_access_token({"sub": "admin"})
    assert isinstance(token, str) and token
```

- [ ] **Step 3.2: Run it to confirm the first test fails**

Run: `pytest tests/test_dashboard_auth.py -v -k secret_key`
Expected: `test_create_access_token_requires_secret_key` FAILS (jose raises its own error, not a `RuntimeError` mentioning `DASHBOARD_SECRET_KEY`). The second test PASSES.

- [ ] **Step 3.3: Add a lazy secret-key accessor and use it**

In `src/dashboard/auth.py`, keep the module-level `SECRET_KEY` line (line 20) for backward compatibility, and add this helper directly beneath the JWT settings block (after line 24):

```python
def _require_secret_key() -> str:
    """Return the JWT secret, raising a clear error if it is not configured.

    Read lazily (not at import) so tests and runtime can set the env var
    before the first auth operation.
    """
    key = os.getenv("DASHBOARD_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "DASHBOARD_SECRET_KEY environment variable must be set "
            "(JWT signing key). Refusing to sign or verify tokens without it."
        )
    return key
```

Then replace the `jwt.encode(...)` call in `create_access_token` (line 120):

```python
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

with:

```python
    encoded_jwt = jwt.encode(to_encode, _require_secret_key(), algorithm=ALGORITHM)
```

and replace the `jwt.decode(...)` call in `get_current_admin` (line 148):

```python
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

with:

```python
        payload = jwt.decode(token, _require_secret_key(), algorithms=[ALGORITHM])
```

Note: `get_current_admin` catches `JWTError` only, so a `RuntimeError` from a missing key surfaces as a 500 — correct behaviour for a server misconfiguration (not a 401).

- [ ] **Step 3.4: Run the auth tests**

Run: `pytest tests/test_dashboard_auth.py tests/test_dashboard_auth_api.py -v`
Expected: all PASS (the API test file sets the env var; confirm no test relied on signing with a `None` key).

- [ ] **Step 3.5: Commit**

```bash
git add src/dashboard/auth.py tests/test_dashboard_auth.py
git commit -m "fix(dashboard): fail fast with clear error when DASHBOARD_SECRET_KEY is unset"
```

---

## Task 4: Refuse wildcard CORS with credentials

**Files:**
- Modify: `src/dashboard/main.py:57-58` (extract origin parsing into a function)
- Test: `tests/test_cors_config.py` (create)

Context: `main.py:58` reads `allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")` and passes it to `CORSMiddleware` with `allow_credentials=True`. A wildcard origin combined with credentials lets any site issue authenticated requests. We extract a pure, testable parser and forbid the wildcard.

- [ ] **Step 4.1: Write the failing test**

Create `tests/test_cors_config.py`:

```python
"""
CORS origin parsing must never combine wildcard with credentialed requests.
"""
import pytest

from src.dashboard.main import resolve_cors_origins


def test_explicit_origins_parsed():
    result = resolve_cors_origins("https://a.example.com, https://b.example.com")
    assert result == ["https://a.example.com", "https://b.example.com"]


def test_unset_defaults_to_localhost_dev_origins():
    result = resolve_cors_origins(None)
    assert "http://localhost:5173" in result
    assert "*" not in result


def test_wildcard_is_rejected():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        resolve_cors_origins("*")
```

- [ ] **Step 4.2: Run it to confirm it fails**

Run: `pytest tests/test_cors_config.py -v`
Expected: FAILS with `ImportError` / `AttributeError` (no `resolve_cors_origins` yet).

- [ ] **Step 4.3: Implement the parser and use it**

In `src/dashboard/main.py`, replace lines 57-58:

```python
# CORS middleware - configure with environment variable
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
```

with:

```python
# CORS middleware - configure with environment variable
def resolve_cors_origins(raw: str | None) -> list[str]:
    """Parse CORS_ORIGINS into an explicit allow-list.

    Wildcard is refused because the app sends credentials (cookies/Authorization),
    and `*` + credentials is both insecure and rejected by browsers.
    """
    if raw is None or not raw.strip():
        logging.getLogger(__name__).warning(
            "CORS_ORIGINS not set; defaulting to localhost dev origins. "
            "Set CORS_ORIGINS explicitly in production."
        )
        return ["http://localhost:5173", "http://localhost:3000"]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins:
        raise ValueError(
            "CORS_ORIGINS must list explicit origins; '*' is not allowed "
            "because the API uses credentialed requests."
        )
    return origins


allowed_origins = resolve_cors_origins(os.getenv("CORS_ORIGINS"))
```

- [ ] **Step 4.4: Run the test**

Run: `pytest tests/test_cors_config.py -v`
Expected: all PASS.

- [ ] **Step 4.5: Commit**

```bash
git add src/dashboard/main.py tests/test_cors_config.py
git commit -m "fix(dashboard): refuse wildcard CORS origin with credentialed requests"
```

---

## Task 5: Serialize payment callbacks per user (double-tap guard)

**Files:**
- Create: `src/bot/utils/user_locks.py`
- Modify: `src/bot/handlers/callbacks.py` (`handle_pay_with_qr` at line 1416, `handle_pay_with_balance` at line 1427)
- Test: `tests/test_user_locks.py` (create)

Context: the bot is a single-process asyncio app. Double-tapping "Pay with QR" can race two PayOS-link creations before the first commits `payos_order_code` (`callbacks.py:1012-1026` TOCTOU window). The balance path is already protected by the atomic conditional UPDATE in `BalanceService`, but we serialize it too for uniformity. An `asyncio.Lock` per `user_id` serializes that user's payment callbacks without blocking other users.

- [ ] **Step 5.1: Write the failing test**

Create `tests/test_user_locks.py`:

```python
"""
Per-user asyncio locks for serializing payment callbacks.
"""
import asyncio

from src.bot.utils.user_locks import get_user_lock


def test_same_user_gets_same_lock():
    assert get_user_lock(111) is get_user_lock(111)


def test_different_users_get_different_locks():
    assert get_user_lock(222) is not get_user_lock(333)


def test_lock_is_asyncio_lock():
    assert isinstance(get_user_lock(444), asyncio.Lock)
```

- [ ] **Step 5.2: Run it to confirm it fails**

Run: `pytest tests/test_user_locks.py -v`
Expected: FAILS (`ModuleNotFoundError: src.bot.utils.user_locks`).

- [ ] **Step 5.3: Implement the lock registry**

Create `src/bot/utils/user_locks.py`:

```python
"""
Per-user asyncio locks for serializing concurrent callback handling.

The customer bot runs on a single event loop, so an asyncio.Lock keyed by
Telegram user id prevents double-tap races (e.g. two payment-link creations)
without blocking other users.
"""
import asyncio

_user_locks: dict[int, asyncio.Lock] = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    """Return a stable asyncio.Lock for the given user id, creating it on first use."""
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock
```

- [ ] **Step 5.4: Run the lock test**

Run: `pytest tests/test_user_locks.py -v`
Expected: all PASS.

- [ ] **Step 5.5: Wrap the QR handler**

In `src/bot/handlers/callbacks.py`, add the import near the other `from src.bot...` imports at the top of the file:

```python
from src.bot.utils.user_locks import get_user_lock
```

Replace `handle_pay_with_qr` (lines 1416-1424):

```python
async def handle_pay_with_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback: pay_qr_{order_id} — user chose to pay via QR transfer.
    Delegates to _create_qr_for_order.
    """
    query = update.callback_query
    await query.answer()
    order_id = query.data.replace("pay_qr_", "")
    await _create_qr_for_order(order_id, update, context, reply_to_query=query)
```

with:

```python
async def handle_pay_with_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback: pay_qr_{order_id} — user chose to pay via QR transfer.
    Delegates to _create_qr_for_order. Serialized per user to prevent
    double-tap creating duplicate payment links.
    """
    query = update.callback_query
    await query.answer()
    order_id = query.data.replace("pay_qr_", "")
    async with get_user_lock(query.from_user.id):
        await _create_qr_for_order(order_id, update, context, reply_to_query=query)
```

- [ ] **Step 5.6: Wrap the balance handler**

In `src/bot/handlers/callbacks.py`, in `handle_pay_with_balance` (starts line 1427), the body opens with `query = update.callback_query` / `await query.answer()` / `user_id = query.from_user.id` / `order_id = ...` and then `session_factory = get_session_factory()`. Wrap everything from `session_factory = get_session_factory()` (line 1444) through the end of the function body (line 1523, the final `else:` branch) in a per-user lock. Concretely, change line 1444 from:

```python
    session_factory = get_session_factory()
    session = session_factory()
    try:
```

to:

```python
    async with get_user_lock(user_id):
        await _pay_with_balance_locked(update, context, query, user_id, order_id)


async def _pay_with_balance_locked(update, context, query, user_id, order_id) -> None:
    """Body of handle_pay_with_balance, run under the per-user lock."""
    import asyncio as _asyncio

    from src.bot.utils.language import t as _t
    from src.database.services.balance_service import BalanceService
    from src.database.services.bot_user_service import BotUserService

    session_factory = get_session_factory()
    session = session_factory()
    try:
```

Leave the remainder of the original function body (from `bot_user_svc = BotUserService(session)` onward) unchanged — it now lives inside `_pay_with_balance_locked`. Remove the now-duplicated `import asyncio as _asyncio` and the `from src.bot.utils.language import t as _t` / `BalanceService` / `BotUserService` imports that were at the top of the original `handle_pay_with_balance` (they moved into the helper). The original `handle_pay_with_balance` now ends after the `async with` block.

IMPORTANT: This is a mechanical extract-method. After editing, open the file and confirm indentation is consistent and no statement was left orphaned between the two functions. If the structure does not cleanly separate, STOP and report.

- [ ] **Step 5.7: Verify import + smoke**

Run: `python -c "import src.bot.handlers.callbacks"`
Expected: no error (module imports cleanly).
Run: `pytest tests/test_user_locks.py tests/test_bot_handlers.py -v`
Expected: all PASS.

- [ ] **Step 5.8: Commit**

```bash
git add src/bot/utils/user_locks.py src/bot/handlers/callbacks.py tests/test_user_locks.py
git commit -m "fix(bot): serialize payment callbacks per user to prevent double-tap races"
```

---

## Task 6: Make IPN order fulfillment idempotent under concurrent webhooks

**Files:**
- Modify: `src/ipn/processor.py` (`_process_payment_success_impl`, around lines 155-208)
- Test: `tests/test_ipn_idempotency.py` (create)

Context: a gateway may deliver the same IPN twice (retries) or two webhooks may arrive nearly simultaneously. `_process_payment_success_impl` checks `status == DELIVERED` (line 178) and returns early, but two concurrent calls can both pass that check, both flip the order to PAID via the non-atomic `update_order_status` (`order_service.py:331`, a read-then-write), and both run fulfillment → duplicate delivery. Pay2S IPN runs in Flask threads and PayOS in an executor thread, so the guard must be an in-process lock keyed by `order_id`, with the DELIVERED check re-evaluated inside the lock.

- [ ] **Step 6.1: Write the failing/guarding test**

Create `tests/test_ipn_idempotency.py`:

```python
"""
The IPN fulfillment lock helper must serialize per order id.
"""
import threading

from src.ipn.processor import _get_order_lock


def test_same_order_gets_same_lock():
    assert _get_order_lock("ORD-1") is _get_order_lock("ORD-1")


def test_different_orders_get_different_locks():
    assert _get_order_lock("ORD-A") is not _get_order_lock("ORD-B")


def test_lock_is_a_lock():
    lock = _get_order_lock("ORD-2")
    assert hasattr(lock, "acquire") and hasattr(lock, "release")
    # A threading.Lock is acquirable/releasable
    assert lock.acquire(blocking=False) is True
    lock.release()
```

- [ ] **Step 6.2: Run it to confirm it fails**

Run: `pytest tests/test_ipn_idempotency.py -v`
Expected: FAILS (`ImportError: cannot import name '_get_order_lock'`).

- [ ] **Step 6.3: Add the per-order lock registry**

In `src/ipn/processor.py`, just below the `run_async` function (after line 91, before the `# Global state manager instance` comment), add:

```python
# Per-order fulfillment locks. The same order id may arrive on two webhook
# threads (gateway retry or near-simultaneous callbacks); these serialize the
# read-status -> deliver -> mark-delivered critical section so a duplicate IPN
# cannot trigger a second delivery.
_order_locks_guard = threading.Lock()
_order_locks: dict[str, threading.Lock] = {}


def _get_order_lock(order_id: str) -> threading.Lock:
    with _order_locks_guard:
        lock = _order_locks.get(order_id)
        if lock is None:
            lock = threading.Lock()
            _order_locks[order_id] = lock
        return lock
```

- [ ] **Step 6.4: Wrap the fulfillment critical section**

In `_process_payment_success_impl`, the order branch currently runs (lines ~166-208): get order → DELIVERED check → amount check → PAID check → `update_order_status(PAID)` → `process_paid_order` → `_run_fulfillment`. Wrap from the order fetch through fulfillment in the per-order lock and re-check DELIVERED inside it. Replace the block starting at `order_service = OrderService(session)` (line 166) down to `return self._run_fulfillment(session, order)` (line 208) with:

```python
            order_service = OrderService(session)
            delivery_service = DeliveryService(session)

            # Serialize fulfillment for this order id across webhook threads.
            with _get_order_lock(order_id):
                # Get order (fresh read inside the lock)
                order = order_service.get_order_by_id(order_id)
                if not order:
                    logger.error(f"Order {order_id} not found in database")
                    return False

                logger.info(
                    f"Found order: user_id={order.user_id}, status={order.status}, "
                    f"total={order.total_amount}"
                )

                # Already delivered (possibly by a concurrent IPN that won the lock)
                if order.status == OrderStatus.DELIVERED:
                    logger.warning(
                        f"Order {order_id} already DELIVERED. Skipping duplicate delivery."
                    )
                    return True

                # Validate amount: IPN amount must match order total
                if amount != order.total_amount:
                    logger.error(
                        f"Amount mismatch! IPN amount: {amount}, "
                        f"Order total: {order.total_amount}. Skipping delivery."
                    )
                    return False

                logger.info(
                    f"Amount validated: IPN amount ({amount}) matches order total "
                    f"({order.total_amount})"
                )

                if order.status == OrderStatus.PAID:
                    logger.warning(
                        f"Order {order_id} already PAID but not delivered. "
                        f"Attempting delivery under lock."
                    )

                # Update order status to PAID
                order_service.update_order_status(
                    order_id=order_id,
                    status=OrderStatus.PAID,
                    payment_transaction_id=transaction_id,
                )

                # Process the order (determine delivery type and trigger delivery)
                if not delivery_service.process_paid_order(order_id):
                    logger.error(f"Failed to process order {order_id}")
                    return False

                return self._run_fulfillment(session, order)
```

This preserves the existing recovery behaviour (a single retried IPN for a stuck-PAID order still re-delivers) while preventing two concurrent IPNs from both delivering: the second one acquires the lock after the first sets DELIVERED and returns early.

- [ ] **Step 6.5: Run the tests**

Run: `pytest tests/test_ipn_idempotency.py tests/test_ipn.py tests/test_delivery_service.py -v`
Expected: all PASS.
Run: `python -c "import src.ipn.processor"`
Expected: no error.

- [ ] **Step 6.6: Commit**

```bash
git add src/ipn/processor.py tests/test_ipn_idempotency.py
git commit -m "fix(ipn): serialize order fulfillment per order id to prevent duplicate delivery"
```

---

## Task 7: Stop creating throwaway event loops in the auto-cancel scheduler thread

**Files:**
- Modify: `src/database/services/auto_cancel_service.py` (constructor + 5 `asyncio.run(...)` sites)
- Modify: `src/bot/tasks/auto_cancel_task.py` (pass + store the main loop)
- Modify: `src/bot/main.py` (capture the running loop via `post_init` and hand it to the task)
- Test: `tests/test_auto_cancel_service.py` (append one test)

Context: `AutoCancelTask` uses `BackgroundScheduler` (`auto_cancel_task.py:26`), which runs jobs in a worker thread with no event loop. `AutoCancelService` calls `asyncio.run(self.bot.send_message(...))` at five sites (lines 124, 144, 284, 378, 397), creating and closing a fresh loop per call. The Telegram `Bot`/httpx client is bound to the bot's main loop, so a fresh loop in another thread risks "Event loop is closed" / cross-loop errors. Fix: schedule those coroutines onto the bot's main loop with `run_coroutine_threadsafe`, falling back to `asyncio.run` only when no main loop is available (preserving current test behaviour).

- [ ] **Step 7.1: Write the failing test**

Append to `tests/test_auto_cancel_service.py` (match the file's existing imports/fixtures — read its top first):

```python
def test_run_coro_falls_back_without_main_loop():
    """With no main loop set, the helper still runs the coroutine (test/back-compat path)."""
    from src.database.services.auto_cancel_service import AutoCancelService

    svc = AutoCancelService(session=None, bot_instance=None)
    ran = {"value": False}

    async def _coro():
        ran["value"] = True

    svc._run_coro(_coro())
    assert ran["value"] is True


def test_run_coro_uses_main_loop_when_running():
    """When a running main loop is provided, the helper schedules onto it."""
    import asyncio
    import threading
    from src.database.services.auto_cancel_service import AutoCancelService

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    try:
        svc = AutoCancelService(session=None, bot_instance=None, main_loop=loop)
        seen = {"loop": None}

        async def _coro():
            seen["loop"] = asyncio.get_running_loop()

        svc._run_coro(_coro())
        assert seen["loop"] is loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=2)
        loop.close()
```

- [ ] **Step 7.2: Run it to confirm it fails**

Run: `pytest tests/test_auto_cancel_service.py -v -k run_coro`
Expected: FAILS (`AutoCancelService.__init__` has no `main_loop` param / no `_run_coro`).

- [ ] **Step 7.3: Add main_loop + helper to the service**

In `src/database/services/auto_cancel_service.py`, change the constructor (lines 29-39):

```python
    def __init__(self, session: Session, bot_instance=None):
        ...
        self.session = session
        self.bot = bot_instance
        self.order_service = OrderService(session)
```

to:

```python
    def __init__(self, session: Session, bot_instance=None, main_loop=None):
        """
        Args:
            session: Database session
            bot_instance: Optional Telegram bot instance for notifications
            main_loop: Optional asyncio loop the bot runs on; coroutines are
                scheduled onto it instead of a throwaway loop in this thread.
        """
        self.session = session
        self.bot = bot_instance
        self.main_loop = main_loop
        self.order_service = OrderService(session)

    def _run_coro(self, coro):
        """Run a bot coroutine from this (non-async) scheduler thread.

        Prefers scheduling onto the bot's main loop (where its httpx client
        lives); falls back to asyncio.run only when no running loop is set.
        """
        loop = self.main_loop
        if loop is not None and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=30)
        return asyncio.run(coro)
```

- [ ] **Step 7.4: Replace the five asyncio.run sites**

In the same file, replace each `asyncio.run(...)` call with `self._run_coro(...)`:

- Line 124: `asyncio.run(self.bot.delete_message(...))` → `self._run_coro(self.bot.delete_message(...))`
- Line 144: `asyncio.run(self.bot.send_message(...))` → `self._run_coro(self.bot.send_message(...))`
- Line 284: `asyncio.run(self.bot.send_message(...))` → `self._run_coro(self.bot.send_message(...))`
- Line 378: `asyncio.run(self.bot.send_message(...))` → `self._run_coro(self.bot.send_message(...))`
- Line 397: `asyncio.run(self.bot.send_message(...))` → `self._run_coro(self.bot.send_message(...))`

Keep the surrounding `try/except` blocks unchanged. Verify with:

Run: `grep -n "asyncio.run(" src/database/services/auto_cancel_service.py`
Expected: no matches remain.

- [ ] **Step 7.5: Thread the loop through the task**

In `src/bot/tasks/auto_cancel_task.py`, change the constructor (lines 16-29) to accept and store a `main_loop`, and pass it when constructing the service (line 37).

Constructor — change signature and add the attribute:

```python
    def __init__(self, bot_instance=None, interval_minutes: int = 1, main_loop=None):
        self.bot = bot_instance
        self.interval_minutes = interval_minutes
        self.main_loop = main_loop
        self.scheduler = BackgroundScheduler()
        self._warned_order_ids: set = set()
        self._warned_topup_ids: set = set()
```

Service construction (line 37) — change:

```python
            auto_cancel_service = AutoCancelService(session, bot_instance=self.bot)
```

to:

```python
            auto_cancel_service = AutoCancelService(
                session, bot_instance=self.bot, main_loop=self.main_loop
            )
```

- [ ] **Step 7.6: Capture the running loop in main.py**

In `src/bot/main.py`, the bot is built at line 252 and the task is started at lines 264-266 inside `main()` (synchronous, before `run_polling`). Move task startup into a `post_init` async hook so it captures the actual loop PTB runs on. Replace lines 263-266:

```python
    # Start auto-cancel task
    auto_cancel_task = AutoCancelTask(bot_instance=bot, interval_minutes=5)
    auto_cancel_task.start()
    logger.info("Auto-cancel task started")
```

with:

```python
    # Start auto-cancel task once the bot's event loop is running, so the task
    # can schedule notification coroutines onto that loop (not a throwaway one).
    auto_cancel_task = AutoCancelTask(bot_instance=bot, interval_minutes=5)

    async def _start_auto_cancel(_application) -> None:
        import asyncio
        auto_cancel_task.main_loop = asyncio.get_running_loop()
        auto_cancel_task.start()
        logger.info("Auto-cancel task started (bound to bot event loop)")

    application.post_init = _start_auto_cancel
```

Confirm `application` is in scope in `main()` (it is — assigned at line 252 via `create_bot_application()`). The `KeyboardInterrupt` handler that calls `auto_cancel_task.stop()` (line 274) still works because `auto_cancel_task` is defined before `run_polling`.

- [ ] **Step 7.7: Run the tests + import check**

Run: `pytest tests/test_auto_cancel_service.py -v`
Expected: all PASS (including the two new ones).
Run: `python -c "import src.bot.main; import src.bot.tasks.auto_cancel_task"`
Expected: no error.

- [ ] **Step 7.8: Commit**

```bash
git add src/database/services/auto_cancel_service.py src/bot/tasks/auto_cancel_task.py src/bot/main.py tests/test_auto_cancel_service.py
git commit -m "fix(bot): schedule auto-cancel notifications on the bot event loop instead of throwaway loops"
```

---

## Task 8: Require admin role on inventory/variation mutation endpoints

**Files:**
- Modify: `src/dashboard/routers/variations.py` (import + mutation endpoints)
- Modify: `src/dashboard/routers/pre_uploaded.py` (import + mutation endpoints)
- Test: `tests/test_variations_api.py` (append one test — read the file's auth fixtures first)

Context: mutation endpoints in these two routers use `Depends(get_current_admin)` (any authenticated account, including viewers) rather than `Depends(require_admin_role)`. `require_admin_role` already exists in `src/dashboard/auth.py:161`. Read (GET) endpoints stay on `get_current_admin`; only state-changing endpoints move to `require_admin_role`.

Endpoints to change (by decorator line → `current_admin` dependency line):
- `variations.py`: POST create (deps at 190), PUT update (253), PUT bulk/stock (327), PUT {id}/stock (374), DELETE {id} (422), PUT bulk/activate (453), PUT bulk/deactivate (490), POST bulk/delete (527).
- `pre_uploaded.py`: POST delete-by-date (307), PUT mark-used (348), PUT mark-unused (396), DELETE {id} (441), POST bulk-delete (469).

Keep on `get_current_admin` (reads): `variations.py` GET list (98/123), GET low-stock, GET {id} (144); `pre_uploaded.py` GET endpoints (197, 241, 263).

- [ ] **Step 8.1: Write the failing test**

Append to `tests/test_variations_api.py` (reuse its existing client/admin/token fixtures; match how it builds a viewer vs admin token — if the file lacks a viewer fixture, create a viewer `Admin` with `role=AdminRole.VIEWER` the same way it creates the admin):

```python
def test_viewer_cannot_create_variation(client, viewer_token, sample_product):
    """A viewer-role token must be forbidden from creating a variation."""
    resp = client.post(
        "/api/variations/",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={
            "product_id": sample_product.id,
            "name": "Should Fail",
            "price": 1000,
            "stock": 1,
        },
    )
    assert resp.status_code == 403


def test_admin_can_create_variation(client, admin_token, sample_product):
    """An admin-role token is allowed (not 403)."""
    resp = client.post(
        "/api/variations/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "product_id": sample_product.id,
            "name": "Allowed Variation",
            "price": 1000,
            "stock": 1,
        },
    )
    assert resp.status_code != 403
```

If the existing fixtures use different names (e.g. `auth_headers` instead of a raw token), adapt these two tests to that style rather than inventing new fixtures. The behaviour asserted (viewer→403, admin→not 403) is what matters.

- [ ] **Step 8.2: Run it to confirm it fails**

Run: `pytest tests/test_variations_api.py -v -k "viewer_cannot_create or admin_can_create"`
Expected: `test_viewer_cannot_create_variation` FAILS (currently returns 201/422, not 403).

- [ ] **Step 8.3: Switch the variations router imports + deps**

In `src/dashboard/routers/variations.py`, change the import (line 9):

```python
from src.dashboard.auth import get_current_admin, get_db
```

to:

```python
from src.dashboard.auth import get_current_admin, require_admin_role, get_db
```

Then in each mutation endpoint listed above, change its dependency line from:

```python
    current_admin=Depends(get_current_admin),
```

to:

```python
    current_admin=Depends(require_admin_role),
```

Change ONLY the mutation endpoints (deps at lines 190, 253, 327, 374, 422, 453, 490, 527). Leave the GET endpoints' deps unchanged. Because line numbers shift as you edit, identify each target by the decorator immediately above it (`@router.post`, `@router.put`, `@router.delete`), not by absolute line number.

- [ ] **Step 8.4: Switch the pre_uploaded router imports + deps**

In `src/dashboard/routers/pre_uploaded.py`, change the import (line 9) the same way:

```python
from src.dashboard.auth import get_current_admin, require_admin_role, get_db
```

Then change the dependency to `Depends(require_admin_role)` on the five mutation endpoints only: POST `/pre-uploaded-products/delete-by-date`, PUT `.../mark-used`, PUT `.../mark-unused`, DELETE `.../{product_id}`, POST `.../bulk-delete`. Leave the three GET endpoints on `get_current_admin`.

- [ ] **Step 8.5: Run the tests**

Run: `pytest tests/test_variations_api.py tests/test_dashboard_auth_api.py -v`
Expected: all PASS, including the two new tests.

- [ ] **Step 8.6: Commit**

```bash
git add src/dashboard/routers/variations.py src/dashboard/routers/pre_uploaded.py tests/test_variations_api.py
git commit -m "fix(dashboard): require admin role for inventory and variation mutations"
```

---

## Task 9: Add a CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

Context: there is a real pytest suite (~45 test files) and a frontend, but nothing runs them automatically. Add a GitHub Actions workflow that runs backend tests and the frontend build/test on every push and PR. Whether the ruff step blocks depends on the Task 0.2 baseline: if `ruff check .` was already clean, make it blocking; if it was dirty, keep `continue-on-error: true` so CI is green now and lint debt can be paid down separately.

- [ ] **Step 9.1: Create the workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run tests
        env:
          DASHBOARD_SECRET_KEY: ci-test-secret
        run: pytest -q
      - name: Lint
        # If the Task 0.2 baseline was clean, delete the next line to make lint blocking.
        continue-on-error: true
        run: ruff check .

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run build
      - run: npm test --if-present
```

- [ ] **Step 9.2: Validate the YAML locally**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no error (valid YAML). If `pyyaml` is not installed, skip — GitHub will validate on push.

- [ ] **Step 9.3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run backend pytest and frontend build/test on push and PR"
```

---

## Task 10: Final verification

**Files:** none modified.

- [ ] **Step 10.1: Run the full suite**

Run: `cd /home/arcrek/MTK_BOT_ORDER && DASHBOARD_SECRET_KEY=ci-test-secret pytest -q 2>&1 | tail -20`
Expected: pass count ≥ the Task 0.1 baseline plus all newly added tests; NO new failures versus baseline.

- [ ] **Step 10.2: Import smoke check**

Run: `python -c "import src.bot.handlers.callbacks, src.ipn.processor, src.dashboard.main, src.bot.main, src.database.services.auto_cancel_service"`
Expected: no error.

- [ ] **Step 10.3: Report**

Summarise: tests added per task, baseline vs final pass count, and any step where reality diverged from the plan (and how it was resolved). If any task was skipped or partially done, say so explicitly.

---

## Self-Review Notes (author)

- **Spec coverage:** All nine review items in the goal are covered — Task 1 (timing-safe HMAC), Task 2 (IPN rejection — the critical forgery hole), Task 3 (secret-key validation), Task 4 (CORS), Task 5 (double-tap guard), Task 6 (concurrent-IPN fulfillment lock), Task 7 (asyncio.run in scheduler thread), Task 8 (role enforcement), Task 9 (CI).
- **Type/name consistency:** helper names are stable across tasks — `_require_secret_key`, `resolve_cors_origins`, `get_user_lock`, `_get_order_lock`, `_run_coro`/`main_loop`. The double-tap extract in Task 5 introduces `_pay_with_balance_locked`; verify the original imports are not left duplicated.
- **Known risk:** Task 5 (extract-method) and Task 8 (line-number drift) are the most error-prone — both instruct the implementer to anchor on structure, not absolute line numbers, and to STOP/report if the structure doesn't match. Task 7 assumes PTB ≥22 supports `application.post_init` assignment (it does).
