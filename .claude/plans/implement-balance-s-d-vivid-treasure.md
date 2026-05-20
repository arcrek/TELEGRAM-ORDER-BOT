# Plan: Implement Balance ("Số dư") wallet feature

## Context

Customers currently pay every order via QR transfer (PayOS default, Pay2S fallback). We want a stored-value wallet so customers can:

1. Top up balance via QR (Nạp tiền)
2. Pay product orders from balance OR from QR (their choice)
3. View their balance and topup history in the bot
4. Receive a Telegram-channel notification when a topup completes (same destinations as `ORDER_PAID`)

Operationally, dashboard admins need a Balances page to inspect each user's balance, see their topup history, and manually add/subtract/set a balance with an audit trail.

The critical constraint is **double-spend safety**: two concurrent balance-paid orders must not both succeed when their combined total exceeds the available balance, and the *same* order must not be paid twice. The implementation uses atomic conditional `UPDATE`s on both the `Order` row and the `BotUser.balance` row inside a single DB transaction so either both succeed or both roll back.

---

## 1. Data model

### Modify `BotUser` (`src/database/models/bot_user.py`)
Add:
```python
balance = Column(BigInteger, nullable=False, default=0, server_default="0")
```
`BigInteger` matches the VND scale used by `Order.total_amount` (avoids overflow on cumulative topups).

### New model `TopupOrder` (`src/database/models/topup_order.py`)
Mirrors `Order` payment fields without items/delivery:
```python
id              String  PK     # "TU" + 8-char hex, e.g. "TUa1b2c3d4"
user_id         BigInteger     # Telegram user ID
bot_user_id     String  FK -> bot_users.id
amount          BigInteger     # VND
status          Enum(TopupStatus)  # pending | paid | cancelled
payment_provider             String
payment_transaction_id       String
payment_message_ids          Text
payos_order_code             BigInteger UNIQUE
payos_payment_link_id        String
payos_checkout_url           Text
created_at, updated_at       DateTime
```
New enum `TopupStatus` in `src/database/models/enums.py`.

### New model `BalanceTransaction` (`src/database/models/balance_transaction.py`)
Append-only audit log of every balance change:
```python
id              String  PK   (uuid)
bot_user_id     String  FK -> bot_users.id
amount          BigInteger   # signed: + for credit, - for debit
balance_after   BigInteger   # snapshot post-change for forensic audit
kind            Enum(BalanceTxKind)
                # TOPUP | ORDER_PAYMENT | ADMIN_ADD | ADMIN_SUBTRACT | ADMIN_SET
reference_id    String NULL  # TopupOrder.id, Order.id, or NULL
admin_id        String NULL  FK -> admins.id  (for ADMIN_* kinds)
reason          Text  NULL   # admin-supplied note
created_at      DateTime
```
New enum `BalanceTxKind` in `src/database/models/enums.py`.

### Extend `NotificationSettings` (`src/database/models/notification_settings.py`)
Add one new column (reuse existing master toggle + whitelist):
```python
topup_notify_on_paid = Column(Boolean, nullable=False, default=False, server_default="false")
```

### Alembic migration `add_balance_wallet_system.py`
- `ALTER TABLE bot_users ADD COLUMN balance BIGINT NOT NULL DEFAULT 0`
- `CREATE TABLE topup_orders ...`
- `CREATE TABLE balance_transactions ...`
- `ALTER TABLE notification_settings ADD COLUMN topup_notify_on_paid BOOLEAN NOT NULL DEFAULT false`
- Follow existing idempotent style in `src/database/migrations/versions/e5f6a7b8c9d0_add_discount_tier_system.py` (inspector checks).

---

## 2. Concurrency safety (CRITICAL)

All balance-affecting operations use **atomic conditional UPDATEs** inside one DB transaction. No read-then-write.

### `BalanceService.pay_order_with_balance(order_id)` — new service
```python
def pay_order_with_balance(self, order_id: str, bot_user: BotUser) -> tuple[bool, str]:
    """
    Returns (success, reason). reason in {'ok','already_processed','insufficient'}.
    Atomic: order PENDING->PAID + balance deduction in one transaction.
    """
    order = self.session.query(Order).filter(Order.id == order_id).first()
    if not order or order.user_id != bot_user.telegram_user_id:
        return False, 'not_found'

    amount = order.total_amount

    # 1) Atomic order status transition. Prevents double-pay of same order.
    r1 = self.session.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == OrderStatus.PENDING)
        .values(status=OrderStatus.PAID,
                payment_provider="balance",
                payment_transaction_id=f"BAL-{uuid4().hex[:12]}")
    )
    if r1.rowcount == 0:
        return False, 'already_processed'

    # 2) Atomic balance deduction. Prevents negative balance under contention.
    r2 = self.session.execute(
        update(BotUser)
        .where(BotUser.id == bot_user.id, BotUser.balance >= amount)
        .values(balance=BotUser.balance - amount)
    )
    if r2.rowcount == 0:
        self.session.rollback()    # also rolls back the Order transition
        return False, 'insufficient'

    self.session.refresh(bot_user)
    self.session.add(BalanceTransaction(
        bot_user_id=bot_user.id, amount=-amount,
        balance_after=bot_user.balance,
        kind=BalanceTxKind.ORDER_PAYMENT,
        reference_id=order_id))
    self.session.commit()
    return True, 'ok'
```
The two atomic checks guarantee the user's stated scenario (two 10k orders, 10k balance) cannot both succeed, AND a fast double-tap on the same order cannot pay twice.

### `BalanceService.credit_topup(topup_id)` — new service
Same atomic pattern for crediting balance on topup success. Idempotent via `WHERE TopupOrder.status == PENDING`.

### `BalanceService.adjust(bot_user_id, action, amount, admin_id, reason)` — admin path
- `add`: `UPDATE bot_users SET balance = balance + :amount`
- `subtract`: `UPDATE bot_users SET balance = balance - :amount WHERE balance >= :amount` (returns False if would go negative)
- `set`: `UPDATE bot_users SET balance = :amount`
All inside a transaction with a `BalanceTransaction` row recording `admin_id` and `reason`.

### Existing race verification
- `OrderService.cancel_order()` (called by `AutoCancelService`) must use `WHERE status='pending'` in its UPDATE. Existing code catches `ValueError` (auto_cancel_service.py:152), so a transition-protected `cancel_order` is required. **Verify during implementation; tighten if needed.**
- `OrderService.generate_payos_order_code()` (order_service.py:45) only checks the `orders` table. Extend the uniqueness check to also exclude `TopupOrder.payos_order_code` so codes don't collide across the two payment tables.

---

## 3. Backend: payment flow integration

### Modify `IPNOrderProcessor` (`src/ipn/processor.py`)
At the top of `_process_payment_success_impl` (line ~144), dispatch by ID prefix or table lookup:
```python
order = order_service.get_order_by_id(order_id)
if order:
    return self._process_product_order(...)   # existing logic, extracted
topup = TopupService(session).get_by_id(order_id)
if topup:
    return self._process_topup_payment(session, topup, transaction_id, amount)
logger.error(...); return False
```
`_process_topup_payment`:
1. Validate `amount == topup.amount` and `topup.status == PENDING`
2. Call `BalanceService.credit_topup(topup_id, transaction_id)` (atomic credit)
3. Delete `topup.payment_message_ids` from the chat (reuse existing pattern at processor.py:203-233)
4. Send the user a "Nạp tiền thành công" message (i18n)
5. Send admin-channel notification via new `OrderNotificationService.send_topup_paid(topup_id)` — reuses `order_notify_enabled` master + new `topup_notify_on_paid` toggle + existing `order_notify_whitelist_chat_ids` whitelist

### Modify PayOS webhook (`src/dashboard/routers/payos_webhook.py:69`)
Currently looks up only `Order.payos_order_code`. Change to: try `Order` first, then `TopupOrder`. Pass the matched record's string ID to `processor.process_payment_success` — the processor's dispatcher handles the rest.

### Modify Pay2S IPN (`src/pay2s/ipn.py`)
Pay2S IPN already keys on the string order_id, so it falls through the processor's new dispatcher with no change.

---

## 4. Bot UI changes

### Persistent keyboard (`src/bot/utils/keyboard.py:8-31`)
Add `Số dư` (Balance) button as a new row.

### New handler `src/bot/handlers/balance.py`
Callbacks (registered in `src/bot/main.py`):
- `balance_view` — Edit message to show current balance, with `[Nạp tiền] [Lịch sử] [Đóng]`
- `balance_history` — Show last 10 `BalanceTransaction` rows (topups + deductions)
- `topup_start` — Show preset amount keyboard `[50k][100k][200k][500k][1M][Tùy chọn]`
- `topup_amount_{value}` — Create TopupOrder for that amount, generate PayOS/Pay2S QR (reuse the QR-rendering logic at callbacks.py:856-1300 — extract into a shared helper `create_payment_for_id(...)` so both order and topup paths use it)
- `topup_custom` — Set `awaiting_topup_amount = True` in `UserState`, prompt text input; text handler reads next message, validates min/max, creates TopupOrder
- Topup amount bounds: **min 10,000 VND, max 50,000,000 VND** — validated in both bot and dashboard (constants in a new `src/database/models/balance_limits.py` or `config/config.py`)

### Modify checkout payment selection (`src/bot/handlers/callbacks.py:746` `handle_payment`)
Insert a new step BEFORE creating the payment QR:
1. After Order row is created with status PENDING (line 825-831), instead of immediately calling PayOS/Pay2S, edit message to show:
   ```
   Phương thức thanh toán
   • Số dư: {balance} VND
   • Cần thanh toán: {total} VND
   [💳 Trả bằng số dư] [🏦 Chuyển khoản QR]
   ```
2. New callbacks:
   - `pay_balance_{order_id}` — Call `BalanceService.pay_order_with_balance(order_id, bot_user)`:
     - On `ok`: Mark messages deleted, call `IPNOrderProcessor._process_product_order_fulfillment(order_id)` to trigger delivery (extract fulfillment-only logic from existing `_process_payment_success_impl` lines 197-276 so balance path and IPN path share it).
     - On `insufficient`: Edit message to "Số dư không đủ" with `[Nạp thêm] [Chuyển khoản QR]` buttons.
     - On `already_processed`: Edit message to "Đơn này đã được xử lý."
   - `pay_qr_{order_id}` — Continue with existing PayOS/Pay2S flow (the part currently at callbacks.py:840+, extracted into a helper that takes an existing order_id rather than creating a new one).
3. Per the UX decision, **the picker is always shown**, even when balance is 0 — tapping Balance with 0 balance falls into the insufficient path and offers Nạp thêm.

### State manager (`src/bot/states/state_manager.py`)
Add to `UserState`:
- `awaiting_topup_amount: bool = False`
- `pending_topup_order_id: Optional[str] = None`
- `pending_payment_order_id: Optional[str] = None`  # for the QR-or-balance step

### Translation keys (`src/i18n/locales/{vi,en}/bot.json`)
Add a `balance.*` namespace: `view_title`, `current_balance`, `topup_button`, `history_button`, `topup_amount_prompt`, `topup_amount_invalid`, `topup_success`, `pay_method_title`, `pay_with_balance`, `pay_with_qr`, `insufficient_balance`, `topup_more_button`, `balance_paid_success`, etc.

### Auto-cancel expired topups
Extend `AutoCancelService.process_expired_orders()` (auto_cancel_service.py:159) — or add a sibling `process_expired_topups()` and call it from `AutoCancelTask.check_and_cancel_expired_orders` — to also cancel PENDING topup orders older than 30 minutes, with `WHERE status='pending'` atomic update.

---

## 5. Dashboard changes

### Backend: new router `src/dashboard/routers/balances.py`
- `GET /api/balances` — paginated list of `BotUser` joined with computed `total_topup` and `last_topup_at`. Query params: `search` (username/first_name/last_name/telegram_user_id), `page`, `per_page`, `sort_by` in `{balance, total_topup, updated_at}`, `sort_order`. Returns the standard `{items, total, page, per_page, total_pages}` envelope used elsewhere (e.g., `products.py`). Dep: `Depends(require_viewer_or_admin)`.
- `GET /api/balances/{bot_user_id}` — single user with their `BalanceTransaction` history and `TopupOrder` history (paginated within).
- `POST /api/balances/{bot_user_id}/adjust` — body `{action: "add"|"subtract"|"set", amount: int, reason: str}`. Calls `BalanceService.adjust(...)` with `admin_id=current_admin.id`. Dep: `Depends(require_admin_role)`.
- Register in `src/dashboard/main.py` with prefix `/api/balances`.

### Backend: new service `src/database/services/balance_service.py`
Houses `pay_order_with_balance`, `credit_topup`, `adjust`, plus read methods (`list_users_with_balance`, `get_user_history`).

### Backend: new service `src/database/services/topup_service.py`
CRUD-style operations on `TopupOrder`: `create_topup`, `get_by_id`, `cancel_topup`, `list_user_topups`.

### Frontend: new page `frontend/src/pages/BalancesPage.tsx`
Follows the `ProductsPage.tsx`/`InventoryPage.tsx` template:
- Filters: search box, sort selector
- Table columns: username, name, telegram_user_id, balance (right-aligned, VND-formatted), total_topup, last_topup_at, Actions (View, Adjust)
- "Adjust" opens `<BalanceAdjustModal>`: radio `[Add | Subtract | Set]`, amount input, reason textarea, submit → `POST /api/balances/{id}/adjust`. Show resulting balance in toast.
- "View" opens `<BalanceDetailDrawer>` showing two tabs: Transactions (full BalanceTransaction list with kind + reason + admin) and Topup Orders (with status + amount + created_at).

### Frontend wiring
- `frontend/src/app/routes.ts`: add `{ path: '/balances', key: 'balances', group: 'operations', iconName: 'Wallet' }`
- `frontend/src/App.tsx`: add `<Route path="/balances" element={<BalancesPage />} />`
- Sidebar will pick it up via the routes config.

---

## 6. Out of scope (v1)

- **Refunds**: if an admin cancels a balance-paid Order after delivery, the balance is **not** auto-refunded. Admin must use the dashboard's Adjust action to manually credit the user. Documented in the dashboard's adjustment modal hint text.
- **Withdrawals / cash-out**: not supported. Balance is one-way (in via topup, out via order payment).
- **Multi-currency**: VND only.

---

## 7. Files to create / modify

### Create
- `src/database/models/topup_order.py`
- `src/database/models/balance_transaction.py`
- `src/database/services/balance_service.py`
- `src/database/services/topup_service.py`
- `src/database/migrations/versions/<hash>_add_balance_wallet_system.py`
- `src/bot/handlers/balance.py`
- `src/dashboard/routers/balances.py`
- `frontend/src/pages/BalancesPage.tsx`
- `frontend/src/pages/balances/BalanceAdjustModal.tsx`
- `frontend/src/pages/balances/BalanceDetailDrawer.tsx`

### Modify
- `src/database/models/bot_user.py` (add `balance`)
- `src/database/models/notification_settings.py` (add `topup_notify_on_paid`)
- `src/database/models/enums.py` (add `TopupStatus`, `BalanceTxKind`)
- `src/database/models/__init__.py` (export new models)
- `src/database/services/order_service.py` (extend `generate_payos_order_code` to check TopupOrder; ensure `cancel_order` uses atomic WHERE status='pending')
- `src/database/services/order_notification_service.py` (add `send_topup_paid` + `_format_topup_message`)
- `src/database/services/auto_cancel_service.py` (process expired topups)
- `src/ipn/processor.py` (dispatch by ID, extract fulfillment helper, add `_process_topup_payment`)
- `src/dashboard/routers/payos_webhook.py` (look up TopupOrder if no Order matches)
- `src/dashboard/main.py` (register balances router)
- `src/bot/handlers/callbacks.py` (insert payment method picker in `handle_payment`, extract QR-creation helper)
- `src/bot/main.py` (register new callback handlers, text handler for custom topup amount)
- `src/bot/states/state_manager.py` (new UserState fields)
- `src/bot/utils/keyboard.py` (add Số dư button)
- `src/i18n/locales/vi/bot.json` and `en/bot.json` (new `balance.*` keys)
- `frontend/src/app/routes.ts` and `frontend/src/App.tsx` (mount new page)

---

## 8. Verification plan

After implementation, before merging:

**DB**
1. `alembic upgrade head` succeeds on a fresh SQLite DB and on a copy of the prod schema (Postgres).
2. Existing `bot_users` rows get `balance=0`; existing `notification_settings` row gets `topup_notify_on_paid=false`.

**Concurrency (CRITICAL)**
3. Unit test in `tests/`: two parallel threads call `pay_order_with_balance` for two different 10k orders on a 10k-balance user. Assert exactly one returns `ok` and the other `insufficient`; final balance is 0; only one order is PAID. (Run against SQLite with `check_same_thread=False`.)
4. Unit test: two parallel calls of `pay_order_with_balance` on the same order (user has surplus balance). Assert one returns `ok` and the other `already_processed`; balance deducted exactly once.
5. Unit test: `adjust(action='subtract')` when amount > balance returns failure without negative balance.

**Topup flow (manual via bot)**
6. From bot: tap Số dư → Nạp tiền → 100k preset → scan QR with Pay2S sandbox / PayOS sandbox → balance increases by 100k after IPN. Channel receives `BALANCE_TOPUP_PAID` notification (only if `topup_notify_on_paid` is enabled in NotificationSettings).
7. Repeat with a custom amount of 7,500 (under min) — bot rejects with i18n error.
8. Place an unpaid topup, wait >30 min: auto-cancel job marks it CANCELLED.

**Order payment flow (manual via bot)**
9. With balance > order total: order checkout shows method picker → pay with balance → message updates to "thanh toán thành công" → pre-uploaded delivery (or UPGRADE prompt) fires exactly once → `ORDER_PAID` channel notification still sent.
10. With balance < order total: picker shown → pay with balance → "insufficient" message with [Nạp thêm] / [QR] → tapping QR creates a payment link successfully.
11. With balance = 0: picker shown anyway → balance path → insufficient flow as above.

**Dashboard (manual)**
12. `/balances` page loads, lists users with non-zero or zero balance, search/sort/pagination work.
13. Open user detail: shows BalanceTransaction history (TOPUP, ORDER_PAYMENT, ADMIN_* entries) and TopupOrder list.
14. Adjust → +50,000 with reason "test credit" → balance updates, audit row appears with admin attribution.
15. Adjust → Subtract more than balance → backend rejects with 400, toast shows error.
16. Adjust → Set to 0 → balance becomes 0, audit row records `ADMIN_SET`.

**Linting / types**
17. `ruff check .`, `mypy src`, `pytest` all pass.
18. `cd frontend && npm run lint && npm test && npm run build` all pass.
