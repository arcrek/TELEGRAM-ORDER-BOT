# User-Based Refund Calculator — Design

**Date:** 2026-06-26
**Status:** Approved (pending spec review)

## Goal

Port the existing order-based refund logic (the bot `/rf` command) into the
dashboard as a **user-based** refund calculator. An admin searches for a user,
sees that user's orders, selects which to refund, enters a per-order duration,
sees the computed refund per order and a total, then either credits the refund
to the user's balance or just marks orders as refunded.

## Flow (admin-facing)

1. Admin searches for a user by Telegram user ID or username, optionally with a
   time range.
2. A table of the user's orders is shown — **all** orders if no time range is
   given, otherwise those within the range.
3. Admin selects one or more orders (ineligible orders cannot be selected).
4. On confirm, the table minifies to only the selected orders; each row shows
   full order information.
5. Admin manually enters a duration per order (days, months, years).
6. The system computes and displays the refund amount for each order and the
   grand total.
7. Two action paths, available per-row and in bulk:
   - **Refund + Credit balance** — sets order `REFUNDED`, credits the refund to
     the user's balance, writes a `BalanceTransaction`.
   - **Mark Refunded** — sets order `REFUNDED` only (no money moves).
   Plus a **Reset** that clears all state and restarts the flow.

## Locked decisions

- **Two distinct buttons** (credit vs status-only), per-row and bulk.
- **Show all orders**, with ineligible ones greyed-out / non-selectable and a
  reason badge.
- **Search by `telegram_user_id`** (digits) or `username` (text).
- **Duration math is fixed**: `total_days = days + months*30 + years*365`
  (matches the bot `/rf` multipliers).
- **Confirm recomputes the amount server-side** from the submitted duration —
  the client-sent amount is never trusted/persisted.

## Existing logic being ported

`src/bot/handlers/refund.py`:
- `_compute_refund(order_total, duration_days, created_at)` →
  `elapsed = max(0, (utcnow() - created_at).days)`,
  `remaining = max(0, duration_days - elapsed)`,
  `refund = min(round(order_total / duration_days * remaining), order_total)`.
- `parse_duration_to_days(text)` and `_UNIT_MAP` (day=1, week=7, month=30,
  year=365).

`BalanceService.refund_order(order_id, refund_amount, telegram_admin_id)`:
atomic guard transitions PAID/PROCESSING/DELIVERED → REFUNDED (sets
`refunded_at`), credits `BotUser.balance`, appends a `BalanceTransaction`
(kind=`REFUND`). Idempotent — a second call returns `(False, 'ineligible')`.

`OrderStatus.REFUNDED` and `Order.refunded_at` already exist — **no migration
needed**.

## Components

### 1. Shared refund logic — `src/utils/refund_calc.py` (new)

Extract the formula + duration parsing so the bot and the dashboard share one
implementation (avoids divergence and the naive-`utcnow()` tz handling drifting
apart):

- `MONTH_DAYS = 30`, `YEAR_DAYS = 365`, and the `_UNIT_MAP` dict.
- `combine_duration(days: int, months: int, years: int) -> int` →
  `days + months*MONTH_DAYS + years*YEAR_DAYS`.
- `parse_duration_to_days(text: str) -> int | None` — moved verbatim from the
  bot handler.
- `compute_refund(order_total: int, duration_days: int, created_at: datetime,
  now: datetime | None = None) -> tuple[int, int, int]` — identical math to
  today; `now` defaults to `datetime.utcnow()` and exists for test determinism.

`src/bot/handlers/refund.py` is updated to import these (its `_compute_refund`
and `parse_duration_to_days` become thin re-exports or direct imports). Bot
behavior is unchanged.

### 2. `BalanceService` changes — `src/database/services/balance_service.py`

- **Extend `refund_order`** to carry dashboard admin attribution. New signature:

  ```python
  def refund_order(
      self,
      order_id: str,
      refund_amount: int,
      *,
      telegram_admin_id: int | None = None,
      admin_id: str | None = None,
      reason: str | None = None,
  ) -> tuple[bool, str]:
  ```

  - When `admin_id` is given, the `BalanceTransaction.admin_id` is set to it and
    `reason` defaults to a dashboard-origin string.
  - When `telegram_admin_id` is given (bot path), behavior is unchanged
    (`admin_id=None`, reason `"Refund via /rf by tg:{id}"`).
  - Existing bot call site passes `telegram_admin_id=` as keyword.

- **New `mark_order_refunded(order_id: str) -> tuple[bool, str]`** — status-only
  transition. Same atomic guard (PAID/PROCESSING/DELIVERED → REFUNDED, sets
  `refunded_at`) but **no balance credit and no transaction row**. Returns
  `'ok' | 'not_found' | 'ineligible'`.

### 3. New router — `src/dashboard/routers/refunds.py` (`/api/refunds`)

Registered in `src/dashboard/main.py`:
`app.include_router(refunds.router, prefix="/api/refunds", tags=["refunds"])`.

Endpoints:

- **`GET /api/refunds/orders`** — query `search`, `start_date`, `end_date`.
  Auth: `require_viewer_or_admin`.
  - Resolves the user: if `search` is all-digits → exact `telegram_user_id`;
    else `username` ILIKE (first match). Returns **404** if no user matches.
  - Lists the user's orders via
    `OrderService.list_orders(user_id=…, start_date=…, end_date=…)` requesting
    all matching rows (a large `per_page`, e.g. 1000, since a single user's
    order count is bounded). No date range ⇒ all orders.
  - Response:
    ```
    {
      "user": {"telegram_user_id": int, "username": str|null,
               "name": str|null, "balance": int},
      "orders": [
        {"id": str, "status": str, "total_amount": int,
         "created_at": ISO, "items": [{"product": str, "variation": str,
                                       "quantity": int}],
         "eligible": bool, "ineligible_reason": str|null}
      ]
    }
    ```
  - `eligible = status in {PAID, PROCESSING, DELIVERED}`; otherwise
    `ineligible_reason` describes why (e.g. "đã hoàn tiền", "chưa thanh toán",
    "đã huỷ").

- **`POST /api/refunds/preview`** — body `{items: [{order_id, days, months,
  years}]}`. Auth: `require_viewer_or_admin`.
  - For each item, loads the order, computes
    `duration_days = combine_duration(...)`, then
    `compute_refund(order.total_amount, duration_days, order.created_at)`.
  - Response: per-order `{order_id, duration_days, elapsed, remaining,
    daily_rate, refund_amount, eligible}` plus `total_refund`. Ineligible or
    `duration_days <= 0` items report `refund_amount = 0`.

- **`POST /api/refunds/confirm`** — body `{items: [{order_id, days, months,
  years, mode: "credit"|"status"}]}`. Auth: `require_admin_role`.
  - Per item:
    - `mode="credit"` → recompute `refund_amount` server-side; if
      `refund_amount <= 0` skip with reason `"no_refund"`; else
      `refund_order(order_id, refund_amount, admin_id=current_admin.id)`.
    - `mode="status"` → `mark_order_refunded(order_id)`.
  - Response: **per-order** `[{order_id, success, reason, refund_amount?,
    new_balance?}]`. Bulk is never all-or-nothing; idempotency comes from the
    atomic guard, so an order refunded in another tab fails cleanly with
    `"ineligible"`.
  - A single-item body backs the per-row buttons; a multi-item body backs the
    bulk "do all" buttons.

### 4. Frontend — `frontend/src/pages/RefundsPage.tsx`

New route `/refunds` (added to `frontend/src/app/routes.ts`) and nav entry. A
single page with a 3-phase local state machine:

1. **Search** — text input (id or username) + two `type="date"` inputs (Orders
   page pattern) + Search button → `GET /api/refunds/orders`.
2. **Select** — user header (name / username / balance) + full orders table
   with row checkboxes. Ineligible rows are greyed-out, checkbox disabled, with
   a reason badge. "Confirm selection" button → phase 3.
3. **Calculate & act** — table minifies to the selected orders; each row shows
   full info (id, items, total, buy date, status) and **days / months / years**
   number inputs. Duration changes trigger `POST /api/refunds/preview` →
   displays per-order refund + grand total. Each row has
   **`[Hoàn + Cộng số dư]`** and **`[Đánh dấu hoàn]`**; a bulk bar has the same
   two for all selected, plus **`[Đặt lại]`** (Reset → phase 1, all state
   cleared). Actions call `POST /api/refunds/confirm`; per-order results update
   each row's status badge inline (success/fail).

Reuses: `apiClient`, `Badge` (already maps `refunded` → neutral variant), the
existing date inputs and table styling, and the dashboard i18n convention used
by the Balances page. Admin-facing Vietnamese strings follow whatever the
dashboard already does (i18n keys if Balances uses them).

## Edge cases

- **User not found** → empty/404 with a clear message; no orders table shown.
- **No time range** → all of the user's orders.
- **`duration_days <= 0`** (all fields zero) → preview shows refund 0; credit is
  refused with reason `"no_refund"`. Status-only mark is still allowed (duration
  is irrelevant to it).
- **Day-boundary drift** — the preview number is advisory; `confirm` recomputes,
  so the credited amount may differ by rounding. The confirm response returns
  the **actual** credited `refund_amount`, which the UI displays.
- **Order goes ineligible between preview and confirm** (e.g. refunded in
  another tab) → that item fails with `"ineligible"`; others still process.
- **`created_at` is naive UTC** — `compute_refund` preserves the existing
  `utcnow()`-based arithmetic exactly.

## Testing

- **Util (`refund_calc`)**: `compute_refund` edge cases (elapsed ≥ duration ⇒ 0,
  cap at total, rounding), `combine_duration`, `parse_duration_to_days` parity
  with the previous bot behavior.
- **Service**: `mark_order_refunded` (atomic transition, idempotent second call
  ⇒ `ineligible`, balance untouched + no tx row); `refund_order` with `admin_id`
  populates `BalanceTransaction.admin_id`.
- **Router**: user resolution by tg-id vs username; date filtering; eligibility
  flags; preview recompute correctness; confirm with mixed eligible/ineligible
  and credit/status modes returns correct per-order outcomes.
- **Bot regression**: existing `refund.py` tests still pass after the extraction.
- **Frontend**: phase-transition tests for `RefundsPage` if the existing pages
  carry vitest coverage; otherwise minimal smoke coverage.
- Follows the existing in-memory SQLite test patterns.

## Out of scope

- No new order status or DB migration.
- No change to the bot `/rf` user-facing behavior.
- No partial/custom refund amount override (refund is always the computed
  prorated value).
