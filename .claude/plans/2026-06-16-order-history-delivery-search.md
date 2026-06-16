# Plan: Search Orders by Delivered Content & Delivery Date

## Goal

In the dashboard **Order History** (Orders page), let an admin find an order by the
**delivered content** that was sent to the customer (fuzzy / partial match), and by the
**delivery date**. Example: paste an account/email/key fragment that was delivered, get
the owning order back.

## Domain facts (verified)

- Delivered content is stored in `pre_uploaded_products.product_data` (Text/JSON), linked to
  the fulfilling order via `PreUploadedProduct.used_by_order_id`, with `is_used = True` and a
  `used_at` timestamp (the delivery moment).
- The current Orders `search` param only matches `Order.id` (`Order.id.ilike(...)`).
- The current backend date filters (`start_date`/`end_date`) match `Order.created_at` and are
  **not even surfaced** in the frontend filter bar today.
- **Delivery date = `PreUploadedProduct.used_at`** (the moment content was delivered), *not*
  `Order.created_at`. This is the date this feature filters on.
- **Scope boundary:** only PRE_UPLOADED orders have stored `product_data`. Delivery-content
  search will never match supplier-fulfilled orders — inherent, not a bug.

## Design decisions (confirmed with user)

1. Search target: delivered **content** text (fuzzy) **and** delivery **date** range.
2. UI: a **separate** "delivered content" search field (distinct from the Order-ID box),
   plus a delivery **date-range** filter.

## Approach

Add three optional, independent backend filters that all target the delivered pre-uploaded row,
combined with a single correlated `EXISTS` subquery (no join, no `.distinct()`):

- `delivery_search` — `product_data ILIKE %term%`
- `delivery_start_date` / `delivery_end_date` — `used_at` range (ISO dates)

Using `EXISTS` (rather than `join + distinct`) keeps each order a single row even when it has
multiple delivered items, leaves `get_total_count` as a plain `func.count(Order.id)`, composes
cleanly with the existing `OrderItem` join used by the `product_id` filter, and puts the content
and date conditions on the **same** delivered row (correct "delivered this content in this
window" semantics).

## Implementation steps

### 1. `src/database/services/order_service.py`
- Add params `delivery_search`, `delivery_start_date`, `delivery_end_date` to both
  `list_orders` and `get_total_count`.
- Build a list of conditions on `PreUploadedProduct` and apply once via
  `query.filter(exists().where(and_(*conds)))`:
  ```python
  from sqlalchemy import exists, and_
  from src.database.models.pre_uploaded_product import PreUploadedProduct

  conds = [
      PreUploadedProduct.used_by_order_id == Order.id,
      PreUploadedProduct.is_used.is_(True),
  ]
  if delivery_search:
      conds.append(PreUploadedProduct.product_data.ilike(f"%{delivery_search}%"))
  if delivery_start_dt:
      conds.append(PreUploadedProduct.used_at >= delivery_start_dt)
  if delivery_end_dt:
      conds.append(PreUploadedProduct.used_at <= delivery_end_dt)
  if len(conds) > 2 or delivery_search:
      query = query.filter(exists().where(and_(*conds)))
  ```
  (Parse the two dates with the same `datetime.fromisoformat(...replace("Z","+00:00"))`
  pattern already used for `start_date`/`end_date`; ignore unparseable values silently, as the
  existing code does. Only apply the `EXISTS` when at least one delivery filter is set.)
- Keep `get_total_count` in lock-step with `list_orders` (same conditions) so counts match.

### 2. `src/dashboard/routers/orders.py`
- Add `delivery_search`, `delivery_start_date`, `delivery_end_date` as `Query(None, ...)`
  params to **`list_orders`** and **`export_orders`**, and pass them through to the service.

### 3. Frontend `frontend/src/pages/OrdersPage.tsx`
- New URL-synced params: `dq` (delivery content), `dfrom`, `dto` (delivery date range), each
  reset `page` on change — mirror the existing `setParam`/debounce pattern used for `q`.
- Filter bar: add a separate `<Input>` ("Tìm theo nội dung đã giao…", Truck icon — already
  imported) and two `<Input type="date">` for the delivery date range.
- Include the three params in both `fetchOrders` and the CSV `export` request when present.

### 4. i18n (`frontend/src/i18n/…`)
- Add translation keys for the new placeholders/labels (vi + en), following existing
  `orders.*` keys. No hardcoded strings.

### 5. Tests
- Backend (`tests/`): extend order-service tests — seed an order with a used
  `PreUploadedProduct`, assert `list_orders(delivery_search=...)` matches by partial content,
  that a non-matching fragment excludes it, that `used_at` range filters work, and that
  `get_total_count` agrees with `list_orders`. Confirm an order with multiple delivered rows
  is returned exactly once.
- Frontend: light vitest coverage if the page already has tests; otherwise rely on backend.

## Out of scope
- No change to existing Order-ID `search` or `created_at` date behavior.
- No new index migration unless profiling shows the `ILIKE` is slow (note for later, not now).

## Execution (per user request)
1. Get plan approval.
2. Delegate implementation to a **Sonnet** subagent.
3. Main loop **reviews** the subagent's changes (correctness, conventions, run `ruff`/tests).
