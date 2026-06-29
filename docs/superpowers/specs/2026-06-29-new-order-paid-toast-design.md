# New-Order Paid Toast Notification — Design

**Date:** 2026-06-29
**Status:** Approved (design); pending spec review

## Goal

Show a toast on **every dashboard page** when an order is newly **paid**, so an admin
knows a sale just happened without watching the Orders page. Format:

> `{username | name} vừa mua {order detail} với giá {total}`

Example: `hùng vừa mua Netflix 1 tháng với giá 50.000đ`

## Decisions (locked)

| Question | Decision |
|----------|----------|
| Trigger event | Order **paid** (the PENDING→PAID transition) |
| Delivery mechanism | **Polling**, every **10s**, from `AppShell` |
| `{order detail}` | **Product + variation**, multiple items joined with `" + "` |

## Why a `paid_at` column (not `updated_at`)

The original sketch filtered `status == PAID` and used `updated_at` as the watermark.
Investigation of the codebase shows this is **incorrect**:

1. **PAID is transient.** The IPN processor flips PAID→DELIVERED
   (`src/ipn/processor.py:591`) or PAID→PROCESSING (`:710`) almost immediately after
   payment. A 10s poll filtering `status == PAID` would **miss most orders** — they are
   already DELIVERED/PROCESSING by the next tick.
2. **`updated_at` re-bumps.** Post-payment flows (UPGRADE delivery: `awaiting_upgrade_info`,
   `upgrade_forwards`) bump `updated_at` long after payment → re-toast of stale orders.
3. **Commit-vs-now race.** `func.now()` is transaction-start time; a row becomes visible
   only at commit. A strict `since = watermark` can permanently skip an order whose
   `now()` precedes the watermark but whose commit lands after a poll.

A dedicated, write-once `paid_at` timestamp eliminates all three: it is set **once** at
the PENDING→PAID transition, never re-bumped, and survives later status changes
(DELIVERED / PROCESSING / REFUNDED). Cost: one nullable column + two one-line additions
at the exact spots that already set `status = PAID`.

## Architecture

Five-process system; the dashboard process owns this feature end to end. The bot/IPN
processes only need to stamp `paid_at` when they mark an order paid.

```
[bot balance pay] ─┐                         poll 10s
[IPN gateway pay] ─┴─> orders.paid_at ──> /api/orders/recent-paid ──> AppShell ──> toast
```

## 1. Database — `Order.paid_at`

`src/database/models/order.py`:

```python
paid_at = Column(DateTime, nullable=True)  # set once at PENDING->PAID; never re-bumped
```

**Migration** (`src/database/migrations/versions/`, autogenerate):
- `down_revision = "k1f2a3b4c5d6"` (current head)
- `upgrade()`: `op.add_column("orders", sa.Column("paid_at", sa.DateTime(), nullable=True))`
- `downgrade()`: `op.drop_column("orders", "paid_at")`
- No backfill — existing paid orders stay `NULL`; they are historical and must not toast.

Apply: `docker compose exec bot alembic upgrade head` (PostgreSQL only).

## 2. Stamp `paid_at` at both paid paths

**Balance path** — `src/database/services/balance_service.py`, the conditional
`update(Order)...values(...)` (~line 61). Add to `.values()`:

```python
.values(
    status=OrderStatus.PAID,
    payment_provider="balance",
    payment_transaction_id=tx_id,
    paid_at=func.now(),
)
```

**IPN / generic path** — `src/database/services/order_service.py`,
`update_order_status` (~line 349). Stamp once when entering PAID:

```python
order.status = status
if status == OrderStatus.PAID and order.paid_at is None:
    order.paid_at = func.now()
```

This covers the IPN gateway flip (`processor.py:226`) and any other caller that
transitions to PAID. `paid_at is None` guard makes it idempotent.

## 3. Backend endpoint — `GET /api/orders/recent-paid`

`src/dashboard/routers/orders.py`.

> **Route ordering:** register `/recent-paid` **before** `@router.get("/{order_id}")`
> (currently line 253), or FastAPI captures it as `order_id="recent-paid"`.

```
GET /api/orders/recent-paid?since=<iso8601>     (since optional)
Auth: Depends(get_current_admin)   # same as all order routes
```

Response:

```json
{
  "server_now": "2026-06-29T10:00:00+00:00",
  "orders": [
    {
      "id": "ORD123",
      "user_id": 456,
      "buyer_username": "hung",
      "buyer_name": "Hùng",
      "total_amount": 50000,
      "items": [
        { "product_name": "Netflix", "variation_name": "1 tháng" }
      ]
    }
  ]
}
```

- `since` omitted → empty `orders` (baseline call); always return `server_now`.
- `since` present → orders with `paid_at > since`, ascending, **limit 50**.
- `server_now` serialized with `to_utc_iso(func.now())` equivalent (DB now), so the client
  watermark tracks server time, not client clock.
- `buyer_username` / `buyer_name` via `service.get_buyer_info_map(...)` (same as `list_orders`).

**New service method** `OrderService.list_recently_paid(since: datetime, limit: int = 50)`:
- `select(Order).where(Order.paid_at.isnot(None), Order.paid_at > since).order_by(Order.paid_at.asc()).limit(limit)`
- `joinedload(Order.items).joinedload(OrderItem.product)` and `.joinedload(OrderItem.variation)` to avoid N+1.
- Endpoint maps each item → `{product_name: item.product.name if item.product else None,
  variation_name: item.variation.name if item.variation else None}`.

## 4. Frontend — poll loop in `AppShell`

`frontend/src/app/layouts/AppShell.tsx`. Mirror the existing todo-count `useEffect`
poll; interval **10_000ms**.

State (refs, no re-render needed for watermark): `sinceRef`, `seenIds: Set<string>`.

```
on first tick:
  res = GET /api/orders/recent-paid            (no since)
  sinceRef = res.server_now
  // no toast — baseline, never spam history on login

every 10s after:
  res = GET /api/orders/recent-paid?since=<sinceRef minus 30s lookback>
  for order in res.orders:
    if order.id not in seenIds:
      seenIds.add(order.id)
      toast.success(buildMessage(order))
  trim seenIds to last ~200 ids
  sinceRef = res.server_now
```

- **30s lookback** (`since = serverNow − 30s`) closes the commit-vs-now race; `seenIds`
  dedups the resulting overlap so no order toasts twice.
- With `paid_at` (write-once), no historical order can re-enter the window, so the
  baseline does **not** need to pre-seed `seenIds` from history.
- Cleanup on unmount (`cancelled` flag + `clearInterval`), same as the todo poll.
- Failures fail silently (`catch {}`), matching the todo poll.

### Toast message (i18n)

Add `newOrderToast` to `frontend/src/i18n/locales/{vi,en}/orders.json`:

```json
// vi
"newOrderToast": "{{buyer}} vừa mua {{detail}} với giá {{total}}"
// en
"newOrderToast": "{{buyer}} just bought {{detail}} for {{total}}"
```

`buildMessage(order)`:
- `buyer = order.buyer_username || order.buyer_name || `#${order.user_id}``
- `detail = order.items.map(i => [i.product_name, i.variation_name].filter(Boolean).join(' ')).join(' + ')`
- `total = formatVndCompact(order.total_amount)`

**Currency format:** the example uses `50.000đ`. `formatCurrency` (Intl VND) emits
`50.000 ₫` (different symbol + space). To match the spec literally, use a small helper:
`formatVndCompact(n) => `${n.toLocaleString('vi-VN')}đ``. Decision: **match the example
(`50.000đ`)**.

Fire via `useToast().success(message, { duration: 8000 })` — `success` is a polite
aria-live variant; 8s gives the admin time to read. Stacked toasts are already supported.

## 5. Testing

**Backend** (`tests/`, in-memory SQLite per existing convention):
- `recent-paid` with `since` returns only orders with `paid_at > since`, ascending,
  including `items[].product_name` / `variation_name` and `server_now`.
- `since` omitted → `orders == []` and `server_now` present.
- An order paid then transitioned DELIVERED/PROCESSING **still** appears (proves it does
  not depend on transient `status == PAID`).
- 403 without auth (mirror existing viewer/auth tests).
- `paid_at` stamped on PENDING→PAID in both `pay_order_with_balance` and
  `update_order_status(PAID)`, and **not** re-stamped on a later status change.

> Compile the new query against `postgresql.dialect()` in at least one test — SQLite
> silently passes constructs Postgres rejects (per project notes).

**Frontend** (`vitest`):
- `buildMessage` formats buyer fallback chain, multi-item `" + "` join, and `50.000đ`.
- A mocked poll response containing a new order id triggers exactly one `toast.success`;
  a repeated id in the lookback window triggers none.

## Out of scope (YAGNI)

- SSE / websockets (polling chosen).
- Backfilling `paid_at` for historical orders.
- Per-admin mute/preferences, sound, browser Notification API.
- Toasting non-paid events (created / refunded / delivered).

## Files touched

| File | Change |
|------|--------|
| `src/database/models/order.py` | add `paid_at` column |
| `src/database/migrations/versions/<new>.py` | add/drop `paid_at` |
| `src/database/services/balance_service.py` | stamp `paid_at` in conditional update |
| `src/database/services/order_service.py` | stamp `paid_at` in `update_order_status`; add `list_recently_paid` |
| `src/dashboard/routers/orders.py` | `/recent-paid` route (before `/{order_id}`) |
| `frontend/src/app/layouts/AppShell.tsx` | 10s poll loop + toast |
| `frontend/src/i18n/locales/{vi,en}/orders.json` | `newOrderToast` |
| `frontend/src/shared/lib/format.ts` | `formatVndCompact` (or inline) |
| `tests/...`, `frontend/src/...test` | backend + frontend tests |
