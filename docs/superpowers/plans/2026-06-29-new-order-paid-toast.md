# New-Order Paid Toast Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a toast on every dashboard page when an order is newly paid, in the form `{username | name} vừa mua {detail} với giá {total}`.

**Architecture:** Add a write-once `Order.paid_at` timestamp stamped at the PENDING→PAID transition in both paid paths (balance + IPN). A new auth'd dashboard endpoint `/api/orders/recent-paid` returns orders paid after a watermark. `AppShell` polls it every 10s and fires a toast per newly-seen paid order.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0, Alembic, FastAPI, React 18 + TypeScript, react-i18next, vitest, pytest.

## Global Constraints

- PostgreSQL only in production; tests use in-memory SQLite via `create_engine_instance(url)`.
- All model changes require an Alembic migration — never modify tables directly.
- DB access only through `src/database/services/` — never raw queries in routers.
- All dashboard order routes require `Depends(get_current_admin)`.
- Translations always via i18n — never hardcode Vietnamese/English strings in components.
- Spec: `docs/superpowers/specs/2026-06-29-new-order-paid-toast-design.md`.
- Current Alembic head: `k1f2a3b4c5d6`.

---

### Task 1: Add `Order.paid_at` column + migration

**Files:**
- Modify: `src/database/models/order.py:70` (near `refunded_at`)
- Create: `src/database/migrations/versions/<autogen>_add_order_paid_at.py`
- Test: `tests/test_order_paid_at_model.py`

**Interfaces:**
- Produces: `Order.paid_at: Column(DateTime, nullable=True)` — write-once paid timestamp.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_order_paid_at_model.py
from src.database.connection import create_engine_instance
from src.database.models.base import Base
from src.database.models.order import Order
from sqlalchemy.orm import sessionmaker


def test_order_has_nullable_paid_at():
    engine = create_engine_instance("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        o = Order(id="O1", user_id=1, total_amount=1000)
        s.add(o)
        s.commit()
        assert o.paid_at is None  # nullable, unset by default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_order_paid_at_model.py -v`
Expected: FAIL — `AttributeError: 'Order' object has no attribute 'paid_at'` (or TypeError on kwarg).

- [ ] **Step 3: Add the column**

In `src/database/models/order.py`, immediately after the `refunded_at` line:

```python
    refunded_at = Column(DateTime, nullable=True)

    # Write-once timestamp of the PENDING->PAID transition. Set in both paid paths
    # (balance + IPN); never re-bumped on later DELIVERED/PROCESSING/REFUNDED changes.
    paid_at = Column(DateTime, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_order_paid_at_model.py -v`
Expected: PASS

- [ ] **Step 5: Create the migration**

Create `src/database/migrations/versions/m3a4b5c6d7e8_add_order_paid_at.py`:

```python
"""add order paid_at

Revision ID: m3a4b5c6d7e8
Revises: k1f2a3b4c5d6
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m3a4b5c6d7e8"
down_revision: Union[str, None] = "k1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("paid_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "paid_at")
```

- [ ] **Step 6: Verify migration chain is linear**

Run: `python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; ScriptDirectory.from_config(Config('alembic.ini')).walk_revisions()" && echo OK`
Expected: prints `OK` with no "Multiple head revisions" error.

- [ ] **Step 7: Commit**

```bash
git add src/database/models/order.py src/database/migrations/versions/m3a4b5c6d7e8_add_order_paid_at.py tests/test_order_paid_at_model.py
git commit -m "feat(orders): add write-once paid_at column + migration"
```

---

### Task 2: Stamp `paid_at` in both paid paths

**Files:**
- Modify: `src/database/services/order_service.py:349-358` (`update_order_status`)
- Modify: `src/database/services/balance_service.py` (the `update(Order)...values(...)` block, ~line 61)
- Test: `tests/test_paid_at_stamping.py`

**Interfaces:**
- Consumes: `Order.paid_at` (Task 1).
- Produces: `paid_at` is set to a non-null `datetime` exactly once, on the first PENDING→PAID transition, in both `OrderService.update_order_status(order_id, OrderStatus.PAID)` and `BalanceService.pay_order_with_balance`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_paid_at_stamping.py
from src.database.connection import create_engine_instance
from src.database.models.base import Base
from src.database.models.order import Order
from src.database.models.enums import OrderStatus
from src.database.services.order_service import OrderService
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine_instance("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_update_status_paid_stamps_paid_at_once():
    s = _session()
    s.add(Order(id="O1", user_id=1, total_amount=1000, status=OrderStatus.PENDING))
    s.commit()
    svc = OrderService(s)

    svc.update_order_status("O1", OrderStatus.PAID)
    first = s.get(Order, "O1").paid_at
    assert first is not None

    # A later status change must NOT re-stamp paid_at.
    svc.update_order_status("O1", OrderStatus.DELIVERED)
    assert s.get(Order, "O1").paid_at == first


def test_non_paid_status_does_not_stamp():
    s = _session()
    s.add(Order(id="O2", user_id=1, total_amount=1000, status=OrderStatus.PENDING))
    s.commit()
    svc = OrderService(s)
    svc.update_order_status("O2", OrderStatus.CANCELLED)
    assert s.get(Order, "O2").paid_at is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_paid_at_stamping.py -v`
Expected: FAIL — `paid_at` stays `None` after PAID transition.

- [ ] **Step 3: Stamp in `update_order_status`**

In `src/database/services/order_service.py`, inside `update_order_status`, replace:

```python
        order.status = status
        if payment_transaction_id:
            order.payment_transaction_id = payment_transaction_id
```

with:

```python
        order.status = status
        if status == OrderStatus.PAID and order.paid_at is None:
            order.paid_at = func.now()
        if payment_transaction_id:
            order.payment_transaction_id = payment_transaction_id
```

Ensure `from sqlalchemy.sql import func` is imported at the top of the file (add it if absent).

- [ ] **Step 4: Stamp in the balance path**

In `src/database/services/balance_service.py`, the conditional `update(Order)` block, add `paid_at=func.now()` to `.values(...)`:

```python
        r1 = self.session.execute(
            update(Order)
            .where(Order.id == order_id, Order.status == OrderStatus.PENDING)
            .values(
                status=OrderStatus.PAID,
                payment_provider="balance",
                payment_transaction_id=tx_id,
                paid_at=func.now(),
            )
        )
```

Ensure `from sqlalchemy.sql import func` (or existing `func` import) is present.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_paid_at_stamping.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Run the existing balance/order suites for regressions**

Run: `pytest tests/ -k "balance or order_service" -q`
Expected: no new failures vs baseline.

- [ ] **Step 7: Commit**

```bash
git add src/database/services/order_service.py src/database/services/balance_service.py tests/test_paid_at_stamping.py
git commit -m "feat(orders): stamp paid_at on PENDING->PAID in both paid paths"
```

---

### Task 3: `list_recently_paid` service method + `/recent-paid` endpoint

**Files:**
- Modify: `src/database/services/order_service.py` (add method)
- Modify: `src/dashboard/routers/orders.py` (add route BEFORE `@router.get("/{order_id}")` at line 253)
- Test: `tests/test_recent_paid_endpoint.py`

**Interfaces:**
- Consumes: `Order.paid_at` (Task 1), `OrderService.get_buyer_info_map(user_ids)` (existing), `to_utc_iso` (existing).
- Produces:
  - `OrderService.list_recently_paid(since: datetime, limit: int = 50) -> list[Order]` — orders with `paid_at` not null and `> since`, ascending by `paid_at`, items+product+variation eager-loaded.
  - `GET /api/orders/recent-paid?since=<iso8601>` → `{"server_now": str, "orders": [{id, user_id, buyer_username, buyer_name, total_amount, items:[{product_name, variation_name}]}]}`. `since` omitted → `orders == []`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recent_paid_endpoint.py
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from src.database.connection import create_engine_instance
from src.database.models.base import Base
from src.database.models.order import Order
from src.database.models.enums import OrderStatus
from src.dashboard.main import app
from src.dashboard.auth import get_db, get_current_admin


def _client_with_db():
    engine = create_engine_instance("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_admin] = lambda: {"username": "admin"}
    return TestClient(app), session


def test_recent_paid_returns_only_orders_after_since():
    client, session = _client_with_db()
    base = datetime(2026, 6, 29, 10, 0, 0)
    # old paid order (before since) and a fresh one (after since)
    session.add(Order(id="OLD", user_id=1, total_amount=1000,
                      status=OrderStatus.DELIVERED, paid_at=base - timedelta(minutes=5)))
    session.add(Order(id="NEW", user_id=2, total_amount=50000,
                      status=OrderStatus.DELIVERED, paid_at=base + timedelta(seconds=5)))
    session.commit()

    since = base.replace(tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/orders/recent-paid?since={since}")
    assert resp.status_code == 200
    body = resp.json()
    assert "server_now" in body
    ids = [o["id"] for o in body["orders"]]
    assert ids == ["NEW"]  # DELIVERED order still counts; old one excluded
    app.dependency_overrides.clear()


def test_recent_paid_without_since_is_empty():
    client, session = _client_with_db()
    resp = client.get("/api/orders/recent-paid")
    assert resp.status_code == 200
    body = resp.json()
    assert body["orders"] == []
    assert "server_now" in body
    app.dependency_overrides.clear()


def test_recent_paid_requires_auth():
    engine = create_engine_instance("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    app.dependency_overrides[get_db] = lambda: iter([session])
    # do NOT override get_current_admin -> real auth runs -> 401/403
    resp = TestClient(app).get("/api/orders/recent-paid?since=2026-06-29T10:00:00+00:00")
    assert resp.status_code in (401, 403)
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recent_paid_endpoint.py -v`
Expected: FAIL — 404 (route missing).

- [ ] **Step 3: Add the service method**

In `src/database/services/order_service.py`, add (ensure `from sqlalchemy.orm import joinedload`, `from sqlalchemy import select`, and `from datetime import datetime` are imported):

```python
    def list_recently_paid(self, since: datetime, limit: int = 50) -> list:
        """Orders paid after `since`, ascending by paid_at, items eager-loaded."""
        from src.database.models.order_item import OrderItem

        stmt = (
            select(Order)
            .where(Order.paid_at.isnot(None), Order.paid_at > since)
            .order_by(Order.paid_at.asc())
            .limit(limit)
            .options(
                joinedload(Order.items).joinedload(OrderItem.product),
                joinedload(Order.items).joinedload(OrderItem.variation),
            )
        )
        return self.session.execute(stmt).unique().scalars().all()
```

- [ ] **Step 4: Add the route (BEFORE `/{order_id}`)**

In `src/dashboard/routers/orders.py`, insert immediately **before** `@router.get("/{order_id}")` (line 253). Ensure `from datetime import datetime` is imported.

```python
@router.get("/recent-paid")
async def recent_paid(
    since: Optional[str] = Query(None, description="ISO8601; return orders paid after this"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Orders newly paid since `since`, for dashboard toast notifications."""
    from sqlalchemy import func as sa_func

    service = OrderService(db)
    server_now = db.execute(select(sa_func.now())).scalar_one()

    orders_out = []
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid 'since' timestamp: {since}",
            )
        # Compare naive-to-naive: DB timestamps are naive UTC.
        if since_dt.tzinfo is not None:
            since_dt = since_dt.astimezone(timezone.utc).replace(tzinfo=None)

        orders = service.list_recently_paid(since_dt)
        buyer_map = service.get_buyer_info_map([o.user_id for o in orders])
        for order in orders:
            orders_out.append({
                "id": order.id,
                "user_id": order.user_id,
                "buyer_username": buyer_map.get(order.user_id, {}).get("username"),
                "buyer_name": buyer_map.get(order.user_id, {}).get("name"),
                "total_amount": order.total_amount,
                "items": [
                    {
                        "product_name": item.product.name if item.product else None,
                        "variation_name": item.variation.name if item.variation else None,
                    }
                    for item in order.items
                ],
            })

    return {"server_now": to_utc_iso(server_now), "orders": orders_out}
```

Add imports at top of `orders.py` if missing: `from datetime import datetime, timezone` and `from sqlalchemy import select`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_recent_paid_endpoint.py -v`
Expected: PASS (all three)

- [ ] **Step 6: Verify query compiles against Postgres dialect**

Add to `tests/test_recent_paid_endpoint.py`:

```python
def test_list_recently_paid_compiles_for_postgres():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy import select
    from src.database.models.order import Order
    stmt = select(Order).where(Order.paid_at.isnot(None), Order.paid_at > datetime(2026, 1, 1))
    # Must not raise for the Postgres dialect.
    str(stmt.compile(dialect=postgresql.dialect()))
```

Run: `pytest tests/test_recent_paid_endpoint.py::test_list_recently_paid_compiles_for_postgres -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/database/services/order_service.py src/dashboard/routers/orders.py tests/test_recent_paid_endpoint.py
git commit -m "feat(orders): /recent-paid endpoint + list_recently_paid service"
```

---

### Task 4: Frontend currency helper + i18n strings

**Files:**
- Modify: `frontend/src/shared/lib/format.ts` (add `formatVndCompact`)
- Modify: `frontend/src/i18n/locales/vi/orders.json`, `frontend/src/i18n/locales/en/orders.json`
- Test: `frontend/src/shared/lib/format.test.ts` (create or append)

**Interfaces:**
- Produces: `formatVndCompact(value: number): string` → e.g. `50000` ⇒ `"50.000đ"`.
- Produces: i18n key `orders.newOrderToast` (nested under the `"orders"` object; the app uses a single `translation` namespace) with params `{buyer, detail, total}`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/shared/lib/format.test.ts
import { describe, it, expect } from 'vitest'
import { formatVndCompact } from './format'

describe('formatVndCompact', () => {
  it('formats VND with dot separators and đ suffix', () => {
    expect(formatVndCompact(50000)).toBe('50.000đ')
    expect(formatVndCompact(1000000)).toBe('1.000.000đ')
    expect(formatVndCompact(0)).toBe('0đ')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/shared/lib/format.test.ts`
Expected: FAIL — `formatVndCompact` is not exported.

- [ ] **Step 3: Add the helper**

In `frontend/src/shared/lib/format.ts`, after `formatCurrency`:

```ts
/** Compact VND for inline copy: 50000 -> "50.000đ" (matches bot/admin phrasing). */
export function formatVndCompact(value: number): string {
  return `${value.toLocaleString('vi-VN')}đ`
}
```

- [ ] **Step 4: Add i18n strings**

The app uses a single `translation` namespace; each file wraps its keys under a top-level object (`{ "orders": { ... } }`). Add the key **inside** the existing `"orders"` object.

`frontend/src/i18n/locales/vi/orders.json` — add inside `"orders"`:

```json
    "newOrderToast": "{{buyer}} vừa mua {{detail}} với giá {{total}}"
```

`frontend/src/i18n/locales/en/orders.json` — add inside `"orders"`:

```json
    "newOrderToast": "{{buyer}} just bought {{detail}} for {{total}}"
```

(Insert as a sibling of the existing keys; mind trailing commas so JSON stays valid. The runtime key path is `orders.newOrderToast`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/shared/lib/format.test.ts`
Expected: PASS

- [ ] **Step 6: Verify JSON validity + build types**

Run: `cd frontend && node -e "require('./src/i18n/locales/vi/orders.json'); require('./src/i18n/locales/en/orders.json'); console.log('OK')"`
Expected: prints `OK`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/shared/lib/format.ts frontend/src/shared/lib/format.test.ts frontend/src/i18n/locales/vi/orders.json frontend/src/i18n/locales/en/orders.json
git commit -m "feat(orders): formatVndCompact helper + newOrderToast i18n strings"
```

---

### Task 5: AppShell poll loop + toast

**Files:**
- Modify: `frontend/src/app/layouts/AppShell.tsx` (add a `useEffect` poll, mirror the todo-count one)
- Test: `frontend/src/app/layouts/newOrderToast.test.ts` (unit-test the message builder + dedup helper)

**Interfaces:**
- Consumes: `apiClient.get` (existing), `useToast()` (existing), `formatVndCompact` (Task 4), `orders:newOrderToast` (Task 4), endpoint `/api/orders/recent-paid` (Task 3).
- Produces: pure helpers `buildToastMessage(order, t)` and `pickNewOrders(orders, seen)` extracted to module scope so they are unit-testable without rendering.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/app/layouts/newOrderToast.test.ts
import { describe, it, expect } from 'vitest'
import { buildToastDetail, buyerLabel, pickNewOrders } from './newOrderToast'

const order = (over = {}) => ({
  id: 'O1', user_id: 9, buyer_username: 'hung', buyer_name: 'Hùng', total_amount: 50000,
  items: [{ product_name: 'Netflix', variation_name: '1 tháng' }], ...over,
})

describe('newOrderToast helpers', () => {
  it('buyerLabel prefers username, then name, then #id', () => {
    expect(buyerLabel(order())).toBe('hung')
    expect(buyerLabel(order({ buyer_username: null }))).toBe('Hùng')
    expect(buyerLabel(order({ buyer_username: null, buyer_name: null }))).toBe('#9')
  })

  it('buildToastDetail joins product+variation, multi with " + "', () => {
    expect(buildToastDetail(order())).toBe('Netflix 1 tháng')
    expect(buildToastDetail(order({ items: [
      { product_name: 'Netflix', variation_name: '1 tháng' },
      { product_name: 'Spotify', variation_name: null },
    ] }))).toBe('Netflix 1 tháng + Spotify')
  })

  it('pickNewOrders returns only unseen ids and mutates the seen set', () => {
    const seen = new Set<string>(['O0'])
    const fresh = pickNewOrders([order({ id: 'O0' }), order({ id: 'O1' })], seen)
    expect(fresh.map(o => o.id)).toEqual(['O1'])
    expect(seen.has('O1')).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/app/layouts/newOrderToast.test.ts`
Expected: FAIL — module `./newOrderToast` not found.

- [ ] **Step 3: Create the helper module**

Create `frontend/src/app/layouts/newOrderToast.ts`:

```ts
import { formatVndCompact } from '../../shared/lib/format'

export interface PaidOrderItem {
  product_name: string | null
  variation_name: string | null
}

export interface PaidOrder {
  id: string
  user_id: number
  buyer_username: string | null
  buyer_name: string | null
  total_amount: number
  items: PaidOrderItem[]
}

export function buyerLabel(o: PaidOrder): string {
  return o.buyer_username || o.buyer_name || `#${o.user_id}`
}

export function buildToastDetail(o: PaidOrder): string {
  return o.items
    .map((i) => [i.product_name, i.variation_name].filter(Boolean).join(' '))
    .filter(Boolean)
    .join(' + ')
}

/** Returns orders whose id is not yet in `seen`; adds the returned ids to `seen`. */
export function pickNewOrders(orders: PaidOrder[], seen: Set<string>): PaidOrder[] {
  const fresh: PaidOrder[] = []
  for (const o of orders) {
    if (!seen.has(o.id)) {
      seen.add(o.id)
      fresh.push(o)
    }
  }
  return fresh
}

export interface NewOrderToastParams { buyer: string; detail: string; total: string }
export function buildToastParams(o: PaidOrder): NewOrderToastParams {
  return { buyer: buyerLabel(o), detail: buildToastDetail(o), total: formatVndCompact(o.total_amount) }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/app/layouts/newOrderToast.test.ts`
Expected: PASS

- [ ] **Step 5: Wire the poll loop into AppShell**

In `frontend/src/app/layouts/AppShell.tsx`:

Add imports:

```ts
import { useTranslation } from 'react-i18next'
import { useToast } from '../../shared/components/Toast'
import { buildToastParams, pickNewOrders, type PaidOrder } from './newOrderToast'
import { useRef } from 'react'
```

Inside `AppShell()`, after the existing hooks:

```ts
  const toast = useToast()
  const { t } = useTranslation()  // single 'translation' namespace; key path is 'orders.newOrderToast'
  const sinceRef = useRef<string | null>(null)
  const seenRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    const LOOKBACK_MS = 30_000

    const poll = async () => {
      try {
        const since = sinceRef.current
        const qs = since
          ? `?since=${encodeURIComponent(new Date(new Date(since).getTime() - LOOKBACK_MS).toISOString())}`
          : ''
        const res = await apiClient.get<{ server_now: string; orders: PaidOrder[] }>(
          `/api/orders/recent-paid${qs}`,
        )
        if (cancelled) return
        const { server_now, orders } = res.data
        if (since === null) {
          // baseline: seed nothing, do not toast history
          sinceRef.current = server_now
          return
        }
        for (const o of pickNewOrders(orders, seenRef.current)) {
          toast.success(t('orders.newOrderToast', buildToastParams(o)), { duration: 8000 })
        }
        // cap memory of the seen-set
        if (seenRef.current.size > 200) {
          seenRef.current = new Set(Array.from(seenRef.current).slice(-200))
        }
        sinceRef.current = server_now
      } catch { /* fail silently */ }
    }

    poll()
    const interval = setInterval(poll, 10_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [toast, t])
```

- [ ] **Step 6: Type-check + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: no errors.

- [ ] **Step 7: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: no new failures vs baseline.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/layouts/AppShell.tsx frontend/src/app/layouts/newOrderToast.ts frontend/src/app/layouts/newOrderToast.test.ts
git commit -m "feat(orders): poll /recent-paid in AppShell and toast new paid orders"
```

---

## Self-Review

**Spec coverage:**
- `paid_at` column + migration → Task 1 ✓
- Stamp at both paid paths, idempotent → Task 2 ✓
- `/recent-paid` endpoint, route ordering before `/{order_id}`, `server_now`, auth, items detail → Task 3 ✓
- `since` omitted → empty; lookback margin → Task 3 (empty) + Task 5 (30s lookback) ✓
- Polling in AppShell @ 10s, baseline no-toast, seen-set dedup + cap → Task 5 ✓
- i18n vi+en, buyer fallback, `" + "` join, `50.000đ` currency → Tasks 4 & 5 ✓
- Postgres-dialect compile test → Task 3 Step 6 ✓
- Tests backend + frontend → all tasks ✓

**Placeholder scan:** none — every code step shows complete content.

**Type consistency:** `PaidOrder`/`PaidOrderItem` defined in `newOrderToast.ts` (Task 5) and consumed by AppShell; `formatVndCompact` defined Task 4, consumed Task 5; `list_recently_paid` signature consistent Task 3 service↔route; `paid_at` consistent Tasks 1→2→3.

## Manual verification (after all tasks)

1. `docker compose exec bot alembic upgrade head` → `paid_at` column exists.
2. Place + pay an order (balance or QR) while a dashboard page is open → toast appears within ~10s: `hùng vừa mua Netflix 1 tháng với giá 50.000đ`.
3. Reload dashboard → no toast for that already-paid order (baseline + seen-set).
4. Switch dashboard language to EN → toast reads `... just bought ... for ...`.
