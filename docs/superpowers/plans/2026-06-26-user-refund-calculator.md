# User-Based Refund Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dashboard refund calculator where an admin searches for a user, picks orders, enters a per-order duration, sees prorated refund amounts, then either credits the refund to the user's balance or marks orders refunded.

**Architecture:** Extract the bot's refund formula into a shared util reused by the bot and a new `/api/refunds` dashboard router. The router exposes order listing (per resolved user), server-authoritative refund preview, and a confirm endpoint that performs per-order credit-or-status actions via `BalanceService`. A new React `RefundsPage` drives a 3-phase flow against those endpoints.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pytest (in-memory SQLite). React 18 + TypeScript, axios, react-i18next, vitest.

## Global Constraints

- DB access only through `src/database/services/` — never raw queries in routers/handlers. (Router resolves users via `BotUserService` and lists orders via `OrderService`; reading `BotUser.balance` for the response uses `BotUserService.get_user_by_telegram_id`.)
- All dashboard service methods are **sync** (this repo's bot/DB layer is synchronous despite CLAUDE.md). Router endpoints are `async def` but call sync services directly.
- Refund formula is fixed and must stay identical between bot and dashboard: `elapsed = max(0, (utcnow() - created_at).days)`, `remaining = max(0, duration_days - elapsed)`, `refund = min(round(order_total / duration_days * remaining), order_total)`; `duration_days <= 0 ⇒ refund 0`.
- Duration combine: `total_days = days + months*30 + years*365`.
- Eligible statuses for refund: `PAID`, `PROCESSING`, `DELIVERED`.
- Refund amount is always recomputed server-side at confirm time; a client-sent amount is never persisted.
- Frontend strings go through the existing i18n system (single `translation` namespace composed from per-feature JSON files); Vietnamese is the default. No hardcoded strings in components.
- Tests use the existing in-memory/file SQLite pattern from `tests/test_orders_api.py`.
- Work happens on branch `feat/user-refund-calculator` (already created).

## File Structure

**Create:**
- `src/utils/refund_calc.py` — shared duration parsing + refund formula.
- `src/dashboard/routers/refunds.py` — `/api/refunds` router (orders / preview / confirm).
- `tests/test_refund_calc.py` — util tests.
- `tests/test_refund_balance_service.py` — `BalanceService` refund/mark tests.
- `tests/test_refunds_api.py` — router tests.
- `frontend/src/pages/refunds/refundsApi.ts` — typed API client + TS types.
- `frontend/src/pages/RefundsPage.tsx` — the page (3-phase flow).
- `frontend/src/i18n/locales/vi/refunds.json`, `frontend/src/i18n/locales/en/refunds.json` — strings.

**Modify:**
- `src/bot/handlers/refund.py` — import shared util instead of local defs.
- `src/database/services/balance_service.py` — extend `refund_order`, add `mark_order_refunded`.
- `src/dashboard/main.py` — register the refunds router.
- `frontend/src/App.tsx` — import + route for `RefundsPage`.
- `frontend/src/app/routes.ts` — nav entry.
- `frontend/src/i18n/config.ts` — wire the `refunds` locale files.
- `frontend/src/i18n/locales/vi/nav.json`, `frontend/src/i18n/locales/en/nav.json` — `nav.refunds` label.

---

### Task 1: Shared refund calculation util

**Files:**
- Create: `src/utils/refund_calc.py`
- Create: `tests/test_refund_calc.py`
- Modify: `src/bot/handlers/refund.py:11-89`

**Interfaces:**
- Produces:
  - `MONTH_DAYS: int = 30`, `YEAR_DAYS: int = 365`
  - `parse_duration_to_days(text: str) -> int | None`
  - `combine_duration(days: int, months: int, years: int) -> int`
  - `compute_refund(order_total: int, duration_days: int, created_at: datetime, now: datetime | None = None) -> tuple[int, int, int]` returning `(elapsed, remaining, refund_amount)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_refund_calc.py`:

```python
"""Tests for the shared prorated-refund calculation util."""
from datetime import datetime, timedelta

from src.utils.refund_calc import (
    MONTH_DAYS,
    YEAR_DAYS,
    combine_duration,
    compute_refund,
    parse_duration_to_days,
)


def test_combine_duration_uses_fixed_multipliers():
    assert combine_duration(5, 0, 0) == 5
    assert combine_duration(0, 1, 0) == MONTH_DAYS
    assert combine_duration(0, 0, 1) == YEAR_DAYS
    assert combine_duration(3, 2, 1) == 3 + 2 * MONTH_DAYS + 1 * YEAR_DAYS


def test_parse_duration_units():
    assert parse_duration_to_days("30") == 30
    assert parse_duration_to_days("4w") == 28
    assert parse_duration_to_days("1m") == 30
    assert parse_duration_to_days("2months") == 60
    assert parse_duration_to_days("1y") == 365


def test_parse_duration_invalid():
    assert parse_duration_to_days("0") is None
    assert parse_duration_to_days("abc") is None
    assert parse_duration_to_days("-5") is None
    assert parse_duration_to_days("10x") is None


def test_compute_refund_half_elapsed():
    created = datetime(2026, 1, 1)
    now = datetime(2026, 1, 16)  # 15 days elapsed
    elapsed, remaining, refund = compute_refund(300000, 30, created, now=now)
    assert elapsed == 15
    assert remaining == 15
    assert refund == 150000


def test_compute_refund_expired_returns_zero():
    created = datetime(2026, 1, 1)
    now = datetime(2026, 3, 1)  # well past 30 days
    elapsed, remaining, refund = compute_refund(300000, 30, created, now=now)
    assert remaining == 0
    assert refund == 0


def test_compute_refund_caps_at_total():
    created = datetime(2026, 1, 10)
    now = datetime(2026, 1, 1)  # future created → elapsed clamps to 0
    _, _, refund = compute_refund(100000, 30, created, now=now)
    assert refund == 100000


def test_compute_refund_zero_duration_is_safe():
    created = datetime(2026, 1, 1)
    now = datetime(2026, 1, 5)
    assert compute_refund(100000, 0, created, now=now) == (0, 0, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_refund_calc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.utils.refund_calc'`

- [ ] **Step 3: Create the util**

Create `src/utils/refund_calc.py`:

```python
"""Shared prorated-refund calculation.

Extracted from src/bot/handlers/refund.py so the bot and the dashboard share
one implementation of the formula and duration parsing. Keep the arithmetic
identical across both call sites.
"""

import re
from datetime import datetime

MONTH_DAYS = 30
YEAR_DAYS = 365

# Regex for duration argument: <n><unit?>  (e.g. "30", "4w", "2months")
_DURATION_RE = re.compile(r"^(\d+)\s*([a-z]*)$", re.IGNORECASE)

# Unit → multiplier (fixed approximations).
_UNIT_MAP: dict[str, int] = {
    "": 1,
    "d": 1,
    "day": 1,
    "days": 1,
    "w": 7,
    "wk": 7,
    "wks": 7,
    "week": 7,
    "weeks": 7,
    "m": MONTH_DAYS,
    "mo": MONTH_DAYS,
    "mon": MONTH_DAYS,
    "month": MONTH_DAYS,
    "months": MONTH_DAYS,
    "y": YEAR_DAYS,
    "yr": YEAR_DAYS,
    "yrs": YEAR_DAYS,
    "year": YEAR_DAYS,
    "years": YEAR_DAYS,
}


def parse_duration_to_days(text: str) -> int | None:
    """Parse a human duration string into a number of days.

    Returns None if the input is invalid or n <= 0.
    """
    m = _DURATION_RE.match(text.strip())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if n <= 0 or unit not in _UNIT_MAP:
        return None
    return n * _UNIT_MAP[unit]


def combine_duration(days: int, months: int, years: int) -> int:
    """Combine day/month/year inputs into total days (month=30, year=365)."""
    return days + months * MONTH_DAYS + years * YEAR_DAYS


def compute_refund(
    order_total: int,
    duration_days: int,
    created_at: datetime,
    now: datetime | None = None,
) -> tuple[int, int, int]:
    """Compute prorated refund.

    Returns (elapsed_days, remaining_days, refund_amount). A non-positive
    duration yields (0, 0, 0). The refund is capped at order_total to guard
    floating-point edge cases.
    """
    if duration_days <= 0:
        return 0, 0, 0
    ref_now = now if now is not None else datetime.utcnow()
    elapsed = max(0, (ref_now - created_at).days)
    remaining = max(0, duration_days - elapsed)
    refund = round(order_total / duration_days * remaining)
    refund = min(refund, order_total)
    return elapsed, remaining, refund
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_refund_calc.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Rewire the bot handler to use the shared util**

In `src/bot/handlers/refund.py`, replace the block from the `import re` line through the end of the local `_compute_refund` definition (the current lines defining `_DURATION_RE`, `_UNIT_MAP`, `parse_duration_to_days`, and `_compute_refund`) with imports. Concretely:

1. Remove `import re` (no longer used here) and remove the `_DURATION_RE`, `_UNIT_MAP`, `parse_duration_to_days`, and `_compute_refund` definitions.
2. Keep the `_ELIGIBLE = {OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.DELIVERED}` line.
3. Add this import alongside the other `src...` imports near the top:

```python
from src.utils.refund_calc import compute_refund as _compute_refund, parse_duration_to_days
```

The existing call sites `_compute_refund(order.total_amount, duration_days, order.created_at)` and `parse_duration_to_days(args[1])` continue to work unchanged (signatures match).

- [ ] **Step 6: Verify the bot handler still imports and the suite is green**

Run: `python -c "import src.bot.handlers.refund"`
Expected: no error (no `NameError` for `re`/`_compute_refund`).

Run: `pytest tests/test_refund_calc.py -q && ruff check src/utils/refund_calc.py src/bot/handlers/refund.py`
Expected: tests PASS, ruff reports no errors.

- [ ] **Step 7: Commit**

```bash
git add src/utils/refund_calc.py tests/test_refund_calc.py src/bot/handlers/refund.py
git commit -m "refactor(refunds): extract shared refund_calc util from bot handler"
```

---

### Task 2: BalanceService — mark_order_refunded + admin attribution

**Files:**
- Modify: `src/database/services/balance_service.py:98-169`
- Create: `tests/test_refund_balance_service.py`

**Interfaces:**
- Consumes: `compute_refund` is not used here; this task only touches persistence.
- Produces:
  - `BalanceService.refund_order(order_id: str, refund_amount: int, telegram_admin_id: int | None = None, *, admin_id: str | None = None, reason: str | None = None) -> tuple[bool, str]`
  - `BalanceService.mark_order_refunded(order_id: str) -> tuple[bool, str]` returning reason in `{'ok','not_found','ineligible'}`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_refund_balance_service.py`:

```python
"""Tests for BalanceService refund + status-only mark, incl. admin attribution."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import *  # noqa: F401,F403 — register all models
from src.database.models.base import Base
from src.database.models.bot_user import BotUser
from src.database.models.order import Order
from src.database.models.balance_transaction import BalanceTransaction
from src.database.models.enums import OrderStatus, BalanceTxKind
from src.database.services.balance_service import BalanceService


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _seed(session, status=OrderStatus.PAID, balance=0):
    user = BotUser(id="u1", telegram_user_id=555, username="bob", balance=balance)
    order = Order(id="ord1", user_id=555, status=status, total_amount=100000)
    session.add_all([user, order])
    session.commit()
    return user, order


def test_refund_order_credits_balance_and_sets_admin_id(session):
    user, _ = _seed(session, balance=20000)
    svc = BalanceService(session)
    ok, reason = svc.refund_order("ord1", 50000, admin_id="admin_1")
    assert (ok, reason) == (True, "ok")
    session.refresh(user)
    assert user.balance == 70000
    tx = session.query(BalanceTransaction).filter_by(reference_id="ord1").one()
    assert tx.kind == BalanceTxKind.REFUND
    assert tx.admin_id == "admin_1"
    assert "admin_1" in (tx.reason or "")
    assert session.query(Order).get("ord1").status == OrderStatus.REFUNDED


def test_refund_order_bot_path_unchanged(session):
    user, _ = _seed(session)
    svc = BalanceService(session)
    ok, reason = svc.refund_order("ord1", 10000, 999)  # positional telegram_admin_id
    assert (ok, reason) == (True, "ok")
    tx = session.query(BalanceTransaction).filter_by(reference_id="ord1").one()
    assert tx.admin_id is None
    assert "tg:999" in (tx.reason or "")


def test_mark_order_refunded_status_only(session):
    user, _ = _seed(session, balance=5000)
    svc = BalanceService(session)
    ok, reason = svc.mark_order_refunded("ord1")
    assert (ok, reason) == (True, "ok")
    session.refresh(user)
    assert user.balance == 5000  # untouched
    assert session.query(BalanceTransaction).count() == 0  # no audit row
    order = session.query(Order).get("ord1")
    assert order.status == OrderStatus.REFUNDED
    assert order.refunded_at is not None


def test_mark_order_refunded_idempotent(session):
    _seed(session)
    svc = BalanceService(session)
    assert svc.mark_order_refunded("ord1") == (True, "ok")
    assert svc.mark_order_refunded("ord1") == (False, "ineligible")


def test_mark_order_refunded_not_found(session):
    svc = BalanceService(session)
    assert svc.mark_order_refunded("missing") == (False, "not_found")


def test_mark_order_refunded_ineligible_status(session):
    _seed(session, status=OrderStatus.PENDING)
    svc = BalanceService(session)
    assert svc.mark_order_refunded("ord1") == (False, "ineligible")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_refund_balance_service.py -v`
Expected: FAIL — `mark_order_refunded` does not exist; `refund_order` rejects the `admin_id` keyword.

- [ ] **Step 3: Extend `refund_order` signature and audit row**

In `src/database/services/balance_service.py`, change the `refund_order` signature (currently `def refund_order(self, order_id, refund_amount, telegram_admin_id)`) to:

```python
    def refund_order(
        self,
        order_id: str,
        refund_amount: int,
        telegram_admin_id: int | None = None,
        *,
        admin_id: str | None = None,
        reason: str | None = None,
    ) -> tuple[bool, str]:
```

Then replace the audit `BalanceTransaction(...)` block (the one with `kind=BalanceTxKind.REFUND`) so the reason and admin attribution are derived:

```python
        # 6. Append audit record.
        if reason is None:
            if admin_id is not None:
                reason = f"Refund via dashboard by admin:{admin_id}"
            else:
                reason = f"Refund via /rf by tg:{telegram_admin_id}"
        self.session.add(
            BalanceTransaction(
                bot_user_id=bot_user.id,
                amount=refund_amount,
                balance_after=new_balance,
                kind=BalanceTxKind.REFUND,
                reference_id=order_id,
                admin_id=admin_id,
                reason=reason,
            )
        )
        self.session.commit()
        return True, "ok"
```

- [ ] **Step 4: Add `mark_order_refunded`**

Immediately after the `refund_order` method in the same class, add:

```python
    def mark_order_refunded(self, order_id: str) -> tuple[bool, str]:
        """Mark an order REFUNDED without crediting balance or writing a tx.

        Same atomic eligibility guard as refund_order. Idempotent — a second
        call on a REFUNDED order returns (False, 'ineligible').

        Returns (success, reason) in {'ok','not_found','ineligible'}.
        """
        order = self.session.execute(
            select(Order).where(Order.id == order_id)
        ).scalar_one_or_none()
        if order is None:
            return False, "not_found"

        eligible = (OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.DELIVERED)
        result = self.session.execute(
            update(Order)
            .where(Order.id == order_id, Order.status.in_(eligible))
            .values(status=OrderStatus.REFUNDED, refunded_at=func.now())
        )
        if result.rowcount == 0:
            return False, "ineligible"

        self.session.commit()
        return True, "ok"
```

(`select`, `update`, `func`, `Order`, `OrderStatus` are already imported in this module — confirm at the top; they are used by the existing `refund_order`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_refund_balance_service.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Confirm the bot call site still type-checks at runtime**

The bot calls `balance_service.refund_order(order_id, refund_amount, user.id)` — `user.id` binds to `telegram_admin_id` positionally. No change needed.

Run: `pytest tests/test_refund_calc.py tests/test_refund_balance_service.py -q && ruff check src/database/services/balance_service.py`
Expected: PASS, no ruff errors.

- [ ] **Step 7: Commit**

```bash
git add src/database/services/balance_service.py tests/test_refund_balance_service.py
git commit -m "feat(refunds): add mark_order_refunded and dashboard admin attribution"
```

---

### Task 3: Refunds router — GET /api/refunds/orders

**Files:**
- Create: `src/dashboard/routers/refunds.py`
- Modify: `src/dashboard/main.py:14-31` (imports) and the `include_router` block (~line 118)
- Create: `tests/test_refunds_api.py`

**Interfaces:**
- Consumes: `BotUserService.get_user_by_telegram_id`, `BotUserService.get_user_by_username`, `OrderService.list_orders`, `to_utc_iso`.
- Produces: `GET /api/refunds/orders?search=&start_date=&end_date=` → `RefundOrdersResponse` with shape `{ user: {telegram_user_id, username, name, balance}, orders: [{id, status, total_amount, created_at, items:[{product,variation,quantity}], eligible, ineligible_reason}] }`. 404 when no user matches.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_refunds_api.py`:

```python
"""Tests for the /api/refunds router."""
import tempfile, os, atexit
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.dashboard.main import app
from src.dashboard.auth import get_password_hash, create_access_token, get_db
from src.database.models import *  # noqa: F401,F403
from src.database.models.base import Base
from src.database.models.admin import Admin, AdminRole
from src.database.models.bot_user import BotUser
from src.database.models.order import Order
from src.database.models.order_item import OrderItem
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.models.enums import OrderStatus, DeliveryType

_f = tempfile.NamedTemporaryFile(delete=False, suffix=".db"); _path = _f.name; _f.close()
atexit.register(lambda: os.path.exists(_path) and os.unlink(_path))
engine = create_engine(f"sqlite:///{_path}", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)


def override_get_db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    s = TestSession()
    yield s
    s.close()


@pytest.fixture
def headers(db: Session):
    admin = Admin(id="admin_1", username="adm", email="a@x.com",
                  password_hash=get_password_hash("pw"), full_name="A",
                  role=AdminRole.ADMIN, is_active=True)
    db.add(admin); db.commit()
    return {"Authorization": f"Bearer {create_access_token(data={'sub': 'adm'})}"}


@pytest.fixture
def seeded(db: Session):
    user = BotUser(id="u1", telegram_user_id=777, username="alice",
                   first_name="Alice", balance=0)
    prod = Product(id="p1", name="Netflix", description="", delivery_type=DeliveryType.PRE_UPLOADED, is_active=True)
    var = ProductVariation(id="v1", product_id="p1", name="1 tháng", price=100000, stock=5, is_active=True)
    paid = Order(id="ordP", user_id=777, status=OrderStatus.PAID, total_amount=100000)
    pending = Order(id="ordX", user_id=777, status=OrderStatus.PENDING, total_amount=50000)
    db.add_all([user, prod, var, paid, pending]); db.commit()
    db.add(OrderItem(id="oi1", order_id="ordP", product_id="p1", variation_id="v1",
                     quantity=1, unit_price=100000, subtotal=100000)); db.commit()
    return user


def test_orders_by_telegram_id(client, headers, seeded):
    r = client.get("/api/refunds/orders", params={"search": "777"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["telegram_user_id"] == 777
    assert body["user"]["username"] == "alice"
    ids = {o["id"]: o for o in body["orders"]}
    assert ids["ordP"]["eligible"] is True
    assert ids["ordX"]["eligible"] is False
    assert ids["ordX"]["ineligible_reason"]  # non-empty
    assert ids["ordP"]["items"][0]["product"] == "Netflix"
    assert ids["ordP"]["items"][0]["variation"] == "1 tháng"


def test_orders_by_username(client, headers, seeded):
    r = client.get("/api/refunds/orders", params={"search": "@alice"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["user"]["telegram_user_id"] == 777


def test_orders_user_not_found(client, headers, seeded):
    r = client.get("/api/refunds/orders", params={"search": "nope"}, headers=headers)
    assert r.status_code == 404


def test_orders_requires_auth(client, seeded):
    r = client.get("/api/refunds/orders", params={"search": "777"})
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_refunds_api.py -v`
Expected: FAIL — 404 on the route (router not mounted yet) so assertions fail / `test_orders_requires_auth` may already pass.

- [ ] **Step 3: Create the router with the GET endpoint**

Create `src/dashboard/routers/refunds.py`:

```python
"""Refunds router — user-based prorated refund calculator for the dashboard.

Admin-facing strings are Vietnamese (consistent with admin-only flows).
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.models.admin import Admin
from src.database.models.enums import OrderStatus
from src.database.services.balance_service import BalanceService
from src.database.services.bot_user_service import BotUserService
from src.database.services.order_service import OrderService
from src.utils.datetime_format import to_utc_iso
from src.utils.refund_calc import combine_duration, compute_refund

router = APIRouter()

_ELIGIBLE = {OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.DELIVERED}

_INELIGIBLE_REASON = {
    OrderStatus.PENDING: "Chưa thanh toán",
    OrderStatus.CANCELLED: "Đã huỷ",
    OrderStatus.REFUNDED: "Đã hoàn tiền",
}


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class RefundOrderItem(BaseModel):
    product: Optional[str]
    variation: Optional[str]
    quantity: int


class RefundOrderRow(BaseModel):
    id: str
    status: str
    total_amount: int
    created_at: Optional[str]
    items: list[RefundOrderItem]
    eligible: bool
    ineligible_reason: Optional[str]


class RefundUser(BaseModel):
    telegram_user_id: int
    username: Optional[str]
    name: Optional[str]
    balance: int


class RefundOrdersResponse(BaseModel):
    user: RefundUser
    orders: list[RefundOrderRow]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _resolve_user(db: Session, search: str):
    """Resolve a BotUser by telegram id (all-digits) or username (else)."""
    s = (search or "").strip()
    if not s:
        return None
    svc = BotUserService(db)
    if s.isdigit():
        return svc.get_user_by_telegram_id(int(s))
    return svc.get_user_by_username(s)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.get("/orders", response_model=RefundOrdersResponse)
async def list_user_orders(
    search: str = Query(..., min_length=1),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_viewer_or_admin),
):
    user = _resolve_user(db, search)
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    orders = OrderService(db).list_orders(
        user_id=user.telegram_user_id,
        start_date=start_date,
        end_date=end_date,
        page=1,
        per_page=1000,
    )

    rows: list[RefundOrderRow] = []
    for o in orders:
        eligible = o.status in _ELIGIBLE
        items = [
            RefundOrderItem(
                product=(it.product.name if it.product else None),
                variation=(it.variation.name if it.variation else None),
                quantity=it.quantity,
            )
            for it in o.items
        ]
        rows.append(
            RefundOrderRow(
                id=o.id,
                status=o.status.value,
                total_amount=o.total_amount,
                created_at=to_utc_iso(o.created_at),
                items=items,
                eligible=eligible,
                ineligible_reason=(
                    None
                    if eligible
                    else _INELIGIBLE_REASON.get(o.status, "Không đủ điều kiện")
                ),
            )
        )

    name = " ".join(p for p in [user.first_name, user.last_name] if p) or None
    return RefundOrdersResponse(
        user=RefundUser(
            telegram_user_id=user.telegram_user_id,
            username=user.username,
            name=name,
            balance=user.balance or 0,
        ),
        orders=rows,
    )
```

- [ ] **Step 4: Register the router in `src/dashboard/main.py`**

Add `refunds` to the routers import block (the multi-name `from src.dashboard.routers import (...)`), and add this line next to the other `include_router` calls (e.g. after the `balances` line):

```python
app.include_router(refunds.router, prefix="/api/refunds", tags=["refunds"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_refunds_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/routers/refunds.py src/dashboard/main.py tests/test_refunds_api.py
git commit -m "feat(refunds): add GET /api/refunds/orders endpoint"
```

---

### Task 4: Refunds router — POST /api/refunds/preview

**Files:**
- Modify: `src/dashboard/routers/refunds.py` (add schemas + endpoint)
- Modify: `tests/test_refunds_api.py` (add tests)

**Interfaces:**
- Consumes: `OrderService.get_order_by_id`, `combine_duration`, `compute_refund`.
- Produces: `POST /api/refunds/preview` body `{items:[{order_id,days,months,years}]}` → `{rows:[{order_id,duration_days,elapsed,remaining,daily_rate,refund_amount,eligible}], total_refund}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_refunds_api.py`:

```python
def test_preview_recomputes_server_side(client, headers, seeded, db):
    # Make the paid order 15 days old against a 30-day duration → ~half refund.
    from datetime import datetime, timedelta
    o = db.query(Order).get("ordP")
    o.created_at = datetime.utcnow() - timedelta(days=15)
    db.commit()

    r = client.post("/api/refunds/preview", headers=headers,
                    json={"items": [{"order_id": "ordP", "days": 0, "months": 1, "years": 0}]})
    assert r.status_code == 200
    body = r.json()
    row = body["rows"][0]
    assert row["duration_days"] == 30
    assert row["elapsed"] == 15
    assert row["refund_amount"] == 50000
    assert body["total_refund"] == 50000


def test_preview_ineligible_is_zero(client, headers, seeded):
    r = client.post("/api/refunds/preview", headers=headers,
                    json={"items": [{"order_id": "ordX", "days": 30}]})
    assert r.status_code == 200
    row = r.json()["rows"][0]
    assert row["eligible"] is False
    assert row["refund_amount"] == 0


def test_preview_unknown_order(client, headers, seeded):
    r = client.post("/api/refunds/preview", headers=headers,
                    json={"items": [{"order_id": "ghost", "days": 30}]})
    assert r.status_code == 200
    assert r.json()["rows"][0]["refund_amount"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_refunds_api.py -k preview -v`
Expected: FAIL — 404/405 on `/api/refunds/preview` (endpoint missing).

- [ ] **Step 3: Add the preview schemas and endpoint**

In `src/dashboard/routers/refunds.py`, add after the existing schemas:

```python
class PreviewItem(BaseModel):
    order_id: str
    days: int = 0
    months: int = 0
    years: int = 0


class PreviewRequest(BaseModel):
    items: list[PreviewItem]


class PreviewRow(BaseModel):
    order_id: str
    duration_days: int
    elapsed: int
    remaining: int
    daily_rate: int
    refund_amount: int
    eligible: bool


class PreviewResponse(BaseModel):
    rows: list[PreviewRow]
    total_refund: int
```

And add the endpoint after `list_user_orders`:

```python
@router.post("/preview", response_model=PreviewResponse)
async def preview_refunds(
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_viewer_or_admin),
):
    order_service = OrderService(db)
    rows: list[PreviewRow] = []
    total = 0
    for item in payload.items:
        order = order_service.get_order_by_id(item.order_id)
        duration_days = combine_duration(item.days, item.months, item.years)
        if order is None:
            rows.append(PreviewRow(order_id=item.order_id, duration_days=duration_days,
                                   elapsed=0, remaining=0, daily_rate=0,
                                   refund_amount=0, eligible=False))
            continue
        eligible = order.status in _ELIGIBLE
        elapsed, remaining, refund = compute_refund(
            order.total_amount, duration_days, order.created_at
        )
        if not eligible:
            refund = 0
        daily_rate = round(order.total_amount / duration_days) if duration_days > 0 else 0
        total += refund
        rows.append(PreviewRow(order_id=item.order_id, duration_days=duration_days,
                               elapsed=elapsed, remaining=remaining,
                               daily_rate=daily_rate, refund_amount=refund,
                               eligible=eligible))
    return PreviewResponse(rows=rows, total_refund=total)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_refunds_api.py -k preview -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/routers/refunds.py tests/test_refunds_api.py
git commit -m "feat(refunds): add POST /api/refunds/preview endpoint"
```

---

### Task 5: Refunds router — POST /api/refunds/confirm

**Files:**
- Modify: `src/dashboard/routers/refunds.py` (add schemas + endpoint)
- Modify: `tests/test_refunds_api.py` (add tests)

**Interfaces:**
- Consumes: `OrderService.get_order_by_id`, `BalanceService.refund_order(admin_id=...)`, `BalanceService.mark_order_refunded`, `BotUserService.get_user_by_telegram_id`, `combine_duration`, `compute_refund`, `require_admin_role`.
- Produces: `POST /api/refunds/confirm` body `{items:[{order_id,days,months,years,mode:"credit"|"status"}]}` → `{results:[{order_id,success,reason,refund_amount?,new_balance?}]}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_refunds_api.py`:

```python
def test_confirm_credit_moves_money(client, headers, seeded, db):
    from datetime import datetime, timedelta
    o = db.query(Order).get("ordP")
    o.created_at = datetime.utcnow() - timedelta(days=15)
    db.commit()

    r = client.post("/api/refunds/confirm", headers=headers, json={"items": [
        {"order_id": "ordP", "days": 0, "months": 1, "years": 0, "mode": "credit"}
    ]})
    assert r.status_code == 200
    res = r.json()["results"][0]
    assert res["success"] is True
    assert res["refund_amount"] == 50000
    assert res["new_balance"] == 50000
    assert db.query(Order).get("ordP").status == OrderStatus.REFUNDED
    bt = db.query(BotUser).filter_by(telegram_user_id=777).one()
    assert bt.balance == 50000


def test_confirm_status_only(client, headers, seeded, db):
    r = client.post("/api/refunds/confirm", headers=headers, json={"items": [
        {"order_id": "ordP", "mode": "status"}
    ]})
    assert r.status_code == 200
    assert r.json()["results"][0]["success"] is True
    assert db.query(Order).get("ordP").status == OrderStatus.REFUNDED
    assert db.query(BotUser).filter_by(telegram_user_id=777).one().balance == 0


def test_confirm_mixed_eligibility(client, headers, seeded):
    r = client.post("/api/refunds/confirm", headers=headers, json={"items": [
        {"order_id": "ordX", "days": 30, "mode": "credit"},  # pending → ineligible
        {"order_id": "ghost", "mode": "status"},             # missing
    ]})
    res = {x["order_id"]: x for x in r.json()["results"]}
    assert res["ordX"]["success"] is False
    assert res["ghost"]["success"] is False
    assert res["ghost"]["reason"] == "not_found"


def test_confirm_zero_refund_skipped(client, headers, seeded, db):
    from datetime import datetime, timedelta
    o = db.query(Order).get("ordP")
    o.created_at = datetime.utcnow() - timedelta(days=400)  # expired
    db.commit()
    r = client.post("/api/refunds/confirm", headers=headers, json={"items": [
        {"order_id": "ordP", "days": 30, "mode": "credit"}
    ]})
    res = r.json()["results"][0]
    assert res["success"] is False
    assert res["reason"] == "no_refund"
    assert db.query(Order).get("ordP").status == OrderStatus.PAID  # unchanged


def test_confirm_requires_admin_role(client, seeded):
    r = client.post("/api/refunds/confirm", json={"items": [
        {"order_id": "ordP", "mode": "status"}
    ]})
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_refunds_api.py -k confirm -v`
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Add the confirm schemas and endpoint**

In `src/dashboard/routers/refunds.py`, add after the preview schemas:

```python
class ConfirmItem(BaseModel):
    order_id: str
    days: int = 0
    months: int = 0
    years: int = 0
    mode: Literal["credit", "status"]


class ConfirmRequest(BaseModel):
    items: list[ConfirmItem]


class ConfirmResult(BaseModel):
    order_id: str
    success: bool
    reason: str
    refund_amount: Optional[int] = None
    new_balance: Optional[int] = None


class ConfirmResponse(BaseModel):
    results: list[ConfirmResult]
```

And add the endpoint after `preview_refunds`:

```python
@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_refunds(
    payload: ConfirmRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_admin_role),
):
    order_service = OrderService(db)
    balance_service = BalanceService(db)
    user_service = BotUserService(db)
    results: list[ConfirmResult] = []

    for item in payload.items:
        order = order_service.get_order_by_id(item.order_id)
        if order is None:
            results.append(ConfirmResult(order_id=item.order_id, success=False,
                                         reason="not_found"))
            continue

        if item.mode == "status":
            ok, reason = balance_service.mark_order_refunded(item.order_id)
            results.append(ConfirmResult(order_id=item.order_id, success=ok, reason=reason))
            continue

        # mode == "credit": recompute amount server-side.
        duration_days = combine_duration(item.days, item.months, item.years)
        _, _, refund = compute_refund(order.total_amount, duration_days, order.created_at)
        if refund <= 0:
            results.append(ConfirmResult(order_id=item.order_id, success=False,
                                         reason="no_refund", refund_amount=0))
            continue

        ok, reason = balance_service.refund_order(
            item.order_id, refund, admin_id=str(current_admin.id)
        )
        new_balance = None
        if ok:
            buyer = user_service.get_user_by_telegram_id(order.user_id)
            new_balance = buyer.balance if buyer else None
        results.append(ConfirmResult(
            order_id=item.order_id, success=ok, reason=reason,
            refund_amount=refund if ok else None, new_balance=new_balance,
        ))

    return ConfirmResponse(results=results)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_refunds_api.py -v`
Expected: PASS (all router tests: orders + preview + confirm)

- [ ] **Step 5: Full backend gate**

Run: `pytest tests/test_refund_calc.py tests/test_refund_balance_service.py tests/test_refunds_api.py -q && ruff check src/dashboard/routers/refunds.py`
Expected: PASS, no ruff errors.

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/routers/refunds.py tests/test_refunds_api.py
git commit -m "feat(refunds): add POST /api/refunds/confirm endpoint"
```

---

### Task 6: Frontend API client, i18n strings, and route wiring

**Files:**
- Create: `frontend/src/pages/refunds/refundsApi.ts`
- Create: `frontend/src/i18n/locales/vi/refunds.json`, `frontend/src/i18n/locales/en/refunds.json`
- Modify: `frontend/src/i18n/config.ts`
- Modify: `frontend/src/i18n/locales/vi/nav.json`, `frontend/src/i18n/locales/en/nav.json`
- Modify: `frontend/src/app/routes.ts`

**Interfaces:**
- Produces (TS):
  - `RefundUser`, `RefundOrderRow`, `RefundOrdersResponse`
  - `PreviewRow`, `PreviewResponse`
  - `ConfirmItem`, `ConfirmResult`, `ConfirmResponse`
  - `fetchUserOrders(search, startDate?, endDate?) => Promise<RefundOrdersResponse>`
  - `previewRefunds(items) => Promise<PreviewResponse>`
  - `confirmRefunds(items) => Promise<ConfirmResponse>`

- [ ] **Step 1: Create the API client module**

Create `frontend/src/pages/refunds/refundsApi.ts`:

```typescript
import { apiClient } from '../../shared/lib/api'

export interface RefundUser {
  telegram_user_id: number
  username: string | null
  name: string | null
  balance: number
}

export interface RefundOrderItem {
  product: string | null
  variation: string | null
  quantity: number
}

export interface RefundOrderRow {
  id: string
  status: string
  total_amount: number
  created_at: string | null
  items: RefundOrderItem[]
  eligible: boolean
  ineligible_reason: string | null
}

export interface RefundOrdersResponse {
  user: RefundUser
  orders: RefundOrderRow[]
}

export interface PreviewRow {
  order_id: string
  duration_days: number
  elapsed: number
  remaining: number
  daily_rate: number
  refund_amount: number
  eligible: boolean
}

export interface PreviewResponse {
  rows: PreviewRow[]
  total_refund: number
}

export interface DurationItem {
  order_id: string
  days: number
  months: number
  years: number
}

export type RefundMode = 'credit' | 'status'

export interface ConfirmItem extends DurationItem {
  mode: RefundMode
}

export interface ConfirmResult {
  order_id: string
  success: boolean
  reason: string
  refund_amount: number | null
  new_balance: number | null
}

export interface ConfirmResponse {
  results: ConfirmResult[]
}

export async function fetchUserOrders(
  search: string,
  startDate?: string,
  endDate?: string,
): Promise<RefundOrdersResponse> {
  const params: Record<string, string> = { search }
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  const res = await apiClient.get<RefundOrdersResponse>('/api/refunds/orders', { params })
  return res.data
}

export async function previewRefunds(items: DurationItem[]): Promise<PreviewResponse> {
  const res = await apiClient.post<PreviewResponse>('/api/refunds/preview', { items })
  return res.data
}

export async function confirmRefunds(items: ConfirmItem[]): Promise<ConfirmResponse> {
  const res = await apiClient.post<ConfirmResponse>('/api/refunds/confirm', { items })
  return res.data
}
```

- [ ] **Step 2: Create the locale files**

Create `frontend/src/i18n/locales/vi/refunds.json`:

```json
{
  "refunds": {
    "title": "Hoàn tiền",
    "searchPlaceholder": "ID Telegram hoặc @username",
    "from": "Từ ngày",
    "to": "Đến ngày",
    "search": "Tìm",
    "userNotFound": "Không tìm thấy người dùng",
    "balance": "Số dư",
    "noOrders": "Người dùng chưa có đơn hàng nào",
    "selectOrders": "Chọn đơn để hoàn tiền",
    "confirmSelection": "Xác nhận lựa chọn",
    "order": "Mã đơn",
    "status": "Trạng thái",
    "total": "Tổng tiền",
    "buyDate": "Ngày mua",
    "items": "Sản phẩm",
    "days": "Ngày",
    "months": "Tháng",
    "years": "Năm",
    "refundAmount": "Số tiền hoàn",
    "totalRefund": "Tổng hoàn",
    "refundAndCredit": "Hoàn + Cộng số dư",
    "markRefunded": "Đánh dấu hoàn",
    "refundAndCreditAll": "Hoàn + Cộng tất cả",
    "markRefundedAll": "Đánh dấu hoàn tất cả",
    "reset": "Đặt lại",
    "done": "Đã hoàn",
    "failed": "Thất bại",
    "confirmCreditMsg": "Hoàn tiền và cộng vào số dư cho các đơn đã chọn?",
    "confirmStatusMsg": "Đánh dấu các đơn đã chọn là đã hoàn (không cộng số dư)?",
    "noEligibleSelected": "Chưa chọn đơn đủ điều kiện nào"
  }
}
```

Create `frontend/src/i18n/locales/en/refunds.json`:

```json
{
  "refunds": {
    "title": "Refunds",
    "searchPlaceholder": "Telegram ID or @username",
    "from": "From",
    "to": "To",
    "search": "Search",
    "userNotFound": "User not found",
    "balance": "Balance",
    "noOrders": "This user has no orders",
    "selectOrders": "Select orders to refund",
    "confirmSelection": "Confirm selection",
    "order": "Order",
    "status": "Status",
    "total": "Total",
    "buyDate": "Buy date",
    "items": "Items",
    "days": "Days",
    "months": "Months",
    "years": "Years",
    "refundAmount": "Refund",
    "totalRefund": "Total refund",
    "refundAndCredit": "Refund + Credit",
    "markRefunded": "Mark refunded",
    "refundAndCreditAll": "Refund + Credit all",
    "markRefundedAll": "Mark all refunded",
    "reset": "Reset",
    "done": "Refunded",
    "failed": "Failed",
    "confirmCreditMsg": "Refund and credit balance for the selected orders?",
    "confirmStatusMsg": "Mark the selected orders as refunded (no balance credit)?",
    "noEligibleSelected": "No eligible orders selected"
  }
}
```

- [ ] **Step 3: Wire the locale files into i18n config**

In `frontend/src/i18n/config.ts`:
1. Add imports next to the other locale imports:

```typescript
import viRefunds from './locales/vi/refunds.json'
import enRefunds from './locales/en/refunds.json'
```

2. Add `...viRefunds,` to the `viTranslations` object and `...enRefunds,` to the `enTranslations` object.

- [ ] **Step 4: Add the nav label**

In `frontend/src/i18n/locales/vi/nav.json`, add to the `"nav"` object: `"refunds": "Hoàn tiền",`
In `frontend/src/i18n/locales/en/nav.json`, add to the `"nav"` object: `"refunds": "Refunds",`

- [ ] **Step 5: Add the route definition**

In `frontend/src/app/routes.ts`, add to the `ROUTES` array within the Operations group (e.g. after the `balances` entry):

```typescript
  { path: '/refunds', key: 'refunds', labelKey: 'nav.refunds', group: 'operations', iconName: 'RotateCcw' },
```

- [ ] **Step 6: Verify the frontend still type-checks/builds**

Run: `cd frontend && npm run lint`
Expected: no new lint errors in the created files. (`RefundsPage` route in `App.tsx` is wired in Task 7; the nav entry renders a link that 404s until then — acceptable mid-plan.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/refunds/refundsApi.ts frontend/src/i18n
git commit -m "feat(refunds): frontend api client, i18n strings, and route definition"
```

---

### Task 7: Frontend RefundsPage (3-phase flow) + route mount

**Files:**
- Create: `frontend/src/pages/RefundsPage.tsx`
- Modify: `frontend/src/App.tsx` (import + `<Route>`)
- Modify: `frontend/src/test/routing.test.tsx` (add refunds route assertion)

**Interfaces:**
- Consumes: everything from `refundsApi.ts` (Task 6), `apiClient`, `Badge`, the confirm-dialog/toast providers already in `App.tsx`.
- Produces: `export function RefundsPage()`.

- [ ] **Step 1: Create the page component**

Create `frontend/src/pages/RefundsPage.tsx`:

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge, type OrderStatus } from '../shared/components/Badge/Badge'
import { useToast } from '../shared/components/Toast'
import {
  fetchUserOrders,
  previewRefunds,
  confirmRefunds,
  type RefundOrdersResponse,
  type RefundOrderRow,
  type PreviewRow,
  type RefundMode,
} from './refunds/refundsApi'

type Phase = 'search' | 'select' | 'calculate'

interface DurationState {
  days: number
  months: number
  years: number
}

const fmtVnd = (n: number) => `${n.toLocaleString('vi-VN')} VND`

export function RefundsPage() {
  const { t } = useTranslation()
  const toast = useToast()

  const [phase, setPhase] = useState<Phase>('search')
  const [search, setSearch] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [loading, setLoading] = useState(false)

  const [data, setData] = useState<RefundOrdersResponse | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [durations, setDurations] = useState<Record<string, DurationState>>({})
  const [preview, setPreview] = useState<Record<string, PreviewRow>>({})
  const [outcome, setOutcome] = useState<Record<string, boolean>>({})

  function reset() {
    setPhase('search')
    setData(null)
    setSelected(new Set())
    setDurations({})
    setPreview({})
    setOutcome({})
  }

  async function doSearch() {
    if (!search.trim()) return
    setLoading(true)
    try {
      const res = await fetchUserOrders(search.trim(), from || undefined, to || undefined)
      setData(res)
      setSelected(new Set())
      setPhase('select')
    } catch (e: any) {
      toast.error(e?.response?.status === 404 ? t('refunds.userNotFound') : String(e))
    } finally {
      setLoading(false)
    }
  }

  function toggle(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function confirmSelection() {
    const init: Record<string, DurationState> = {}
    selected.forEach(id => { init[id] = { days: 0, months: 0, years: 0 } })
    setDurations(init)
    setPreview({})
    setOutcome({})
    setPhase('calculate')
  }

  function setDuration(id: string, patch: Partial<DurationState>) {
    setDurations(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }))
  }

  async function recompute(ids: string[]) {
    const items = ids.map(id => ({ order_id: id, ...durations[id] }))
    try {
      const res = await previewRefunds(items)
      setPreview(prev => {
        const next = { ...prev }
        res.rows.forEach(r => { next[r.order_id] = r })
        return next
      })
    } catch (e) {
      toast.error(String(e))
    }
  }

  async function doConfirm(ids: string[], mode: RefundMode) {
    if (ids.length === 0) { toast.error(t('refunds.noEligibleSelected')); return }
    const items = ids.map(id => ({ order_id: id, ...durations[id], mode }))
    try {
      const res = await confirmRefunds(items)
      setOutcome(prev => {
        const next = { ...prev }
        res.results.forEach(r => { next[r.order_id] = r.success })
        return next
      })
      const ok = res.results.filter(r => r.success).length
      toast.success(`${ok}/${res.results.length}`)
    } catch (e) {
      toast.error(String(e))
    }
  }

  const selectedOrders: RefundOrderRow[] =
    data?.orders.filter(o => selected.has(o.id)) ?? []
  const eligibleSelectedIds = selectedOrders.filter(o => o.eligible).map(o => o.id)
  const totalRefund = eligibleSelectedIds.reduce(
    (sum, id) => sum + (preview[id]?.refund_amount ?? 0), 0)

  return (
    <div style={{ padding: 24 }}>
      <h1>{t('refunds.title')}</h1>

      {/* Phase 1: search */}
      <div style={{ display: 'flex', gap: 8, margin: '16px 0', flexWrap: 'wrap' }}>
        <input
          placeholder={t('refunds.searchPlaceholder')}
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()}
        />
        <input type="date" value={from} onChange={e => setFrom(e.target.value)} aria-label={t('refunds.from')} />
        <input type="date" value={to} onChange={e => setTo(e.target.value)} aria-label={t('refunds.to')} />
        <button onClick={doSearch} disabled={loading}>{t('refunds.search')}</button>
        {data && <button onClick={reset}>{t('refunds.reset')}</button>}
      </div>

      {data && (
        <div style={{ marginBottom: 12 }}>
          <strong>{data.user.name || data.user.username || data.user.telegram_user_id}</strong>
          {data.user.username && <span> (@{data.user.username})</span>}
          <span> — {t('refunds.balance')}: {fmtVnd(data.user.balance)}</span>
        </div>
      )}

      {/* Phase 2: select all orders */}
      {phase === 'select' && data && (
        <>
          {data.orders.length === 0 && <p>{t('refunds.noOrders')}</p>}
          {data.orders.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th></th>
                  <th>{t('refunds.order')}</th>
                  <th>{t('refunds.items')}</th>
                  <th>{t('refunds.total')}</th>
                  <th>{t('refunds.status')}</th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map(o => (
                  <tr key={o.id} style={{ opacity: o.eligible ? 1 : 0.5 }}>
                    <td>
                      <input
                        type="checkbox"
                        disabled={!o.eligible}
                        checked={selected.has(o.id)}
                        onChange={() => toggle(o.id)}
                      />
                    </td>
                    <td>{o.id}</td>
                    <td>{o.items.map(i => `${i.product ?? ''} ${i.variation ?? ''} ×${i.quantity}`).join(', ')}</td>
                    <td>{fmtVnd(o.total_amount)}</td>
                    <td>
                      <Badge status={o.status as OrderStatus} size="sm">{o.status}</Badge>
                      {!o.eligible && o.ineligible_reason && <span> — {o.ineligible_reason}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <button
            style={{ marginTop: 12 }}
            disabled={eligibleSelectedFromSet(selected, data) === 0}
            onClick={confirmSelection}
          >
            {t('refunds.confirmSelection')}
          </button>
        </>
      )}

      {/* Phase 3: calculate + act */}
      {phase === 'calculate' && data && (
        <>
          <table>
            <thead>
              <tr>
                <th>{t('refunds.order')}</th>
                <th>{t('refunds.items')}</th>
                <th>{t('refunds.total')}</th>
                <th>{t('refunds.days')}</th>
                <th>{t('refunds.months')}</th>
                <th>{t('refunds.years')}</th>
                <th>{t('refunds.refundAmount')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {selectedOrders.map(o => {
                const d = durations[o.id] ?? { days: 0, months: 0, years: 0 }
                return (
                  <tr key={o.id}>
                    <td>{o.id}</td>
                    <td>{o.items.map(i => `${i.product ?? ''} ${i.variation ?? ''} ×${i.quantity}`).join(', ')}</td>
                    <td>{fmtVnd(o.total_amount)}</td>
                    {(['days', 'months', 'years'] as const).map(unit => (
                      <td key={unit}>
                        <input
                          type="number" min={0} style={{ width: 60 }}
                          value={d[unit]}
                          onChange={e => setDuration(o.id, { [unit]: Number(e.target.value) || 0 })}
                          onBlur={() => recompute([o.id])}
                        />
                      </td>
                    ))}
                    <td>{fmtVnd(preview[o.id]?.refund_amount ?? 0)}</td>
                    <td>
                      {outcome[o.id] === true && <Badge status="refunded" size="sm">{t('refunds.done')}</Badge>}
                      {outcome[o.id] === false && <span style={{ color: 'var(--danger-500)' }}>{t('refunds.failed')}</span>}
                      {outcome[o.id] === undefined && (
                        <>
                          <button onClick={() => doConfirm([o.id], 'credit')}>{t('refunds.refundAndCredit')}</button>
                          <button onClick={() => doConfirm([o.id], 'status')}>{t('refunds.markRefunded')}</button>
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <strong>{t('refunds.totalRefund')}: {fmtVnd(totalRefund)}</strong>
            <button onClick={() => doConfirm(eligibleSelectedIds, 'credit')}>{t('refunds.refundAndCreditAll')}</button>
            <button onClick={() => doConfirm(eligibleSelectedIds, 'status')}>{t('refunds.markRefundedAll')}</button>
            <button onClick={reset}>{t('refunds.reset')}</button>
          </div>
        </>
      )}
    </div>
  )
}

function eligibleSelectedFromSet(selected: Set<string>, data: RefundOrdersResponse): number {
  return data.orders.filter(o => selected.has(o.id) && o.eligible).length
}
```

> Note: this page uses plain elements + inline styles for clarity; if the repo
> exposes shared `Table`/`Button`/`Input` primitives (as Balances/Orders use),
> swap them in to match the dark theme. The logic and i18n keys stay the same.

- [ ] **Step 2: Mount the route in `App.tsx`**

In `frontend/src/App.tsx`:
1. Add the import next to the other page imports:

```typescript
import { RefundsPage } from './pages/RefundsPage'
```

2. Add the route inside the protected `<Route path="/">` block (e.g. after the `balances` route):

```tsx
          <Route path="refunds" element={<RefundsPage />} />
```

- [ ] **Step 3: Add a routing test**

In `frontend/src/test/routing.test.tsx`, follow the existing pattern in that file to add an assertion that navigating to `/refunds` renders the page (assert on the `refunds.title` text or a stable element). Mirror however the existing tests render with the router + i18n provider.

- [ ] **Step 4: Verify build, lint, and tests**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: lint clean, vitest passes (including the new routing assertion), production build succeeds.

- [ ] **Step 5: Manual verification**

Start the dashboard API (`python run_dashboard.py`) and the frontend (`cd frontend && npm run dev`). Log in, open **Hoàn tiền** in the nav, and walk the flow:
1. Search a user by Telegram ID and by `@username`; confirm a bad search shows "Không tìm thấy người dùng".
2. Confirm all orders show; ineligible ones are greyed and non-selectable with a reason.
3. Select orders → Confirm selection → table minifies to the selection.
4. Enter days/months/years → refund amount + total update.
5. Per-row `[Hoàn + Cộng số dư]` credits the user (verify balance changed on the Balances page); `[Đánh dấu hoàn]` only flips status.
6. Bulk buttons act on all eligible selected; `[Đặt lại]` returns to phase 1 cleared.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/RefundsPage.tsx frontend/src/App.tsx frontend/src/test/routing.test.tsx
git commit -m "feat(refunds): add RefundsPage with search/select/calculate flow"
```

---

## Self-Review

**Spec coverage:**
- Search user by id/username + time range → Task 3 (`/orders`, `_resolve_user`), Task 7 (phase 1).
- Table of all orders, show-all with ineligible disabled → Task 3 (eligibility flags), Task 7 (phase 2 greyed/disabled).
- Select orders → confirm → minify to selected with full info → Task 7 (phase 2→3).
- Manual duration per order (days/months/years) → Task 6 (types), Task 7 (inputs), `combine_duration` Task 1.
- Compute + display per-order refund and total → Task 4 (`/preview`), Task 7 (preview state + total).
- Mark all refunded + per-order button (two modes) → Task 5 (`/confirm`), Task 7 (per-row + bulk buttons).
- Reset → Task 7 (`reset()`).
- Credit-vs-status two-button behavior → Task 2 (`mark_order_refunded` + `refund_order`), Task 5.
- Server-authoritative recompute → Task 4/Task 5 recompute from duration.
- Shared formula (no divergence) → Task 1.

**Placeholder scan:** No TBD/TODO; all code blocks complete. The only soft step is Task 7 Step 3 (routing test), which is intentionally adaptive because the exact render harness in `routing.test.tsx` must be mirrored — the implementer reads that file and follows its pattern.

**Type consistency:** `RefundOrdersResponse`/`RefundOrderRow`/`PreviewRow`/`ConfirmItem`/`ConfirmResult` match between `refundsApi.ts` (Task 6) and the router schemas (Tasks 3–5). `mark_order_refunded` and `refund_order(admin_id=...)` signatures match between Task 2 (definition) and Task 5 (call). `combine_duration`/`compute_refund` signatures match between Task 1 and Tasks 4/5.

## Out of scope
- No new order status or DB migration (`OrderStatus.REFUNDED` + `refunded_at` already exist).
- No change to bot `/rf` user-facing behavior.
- No custom/partial refund amount override.
