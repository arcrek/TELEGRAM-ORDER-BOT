# `/export` Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a customer download their purchased pre-uploaded content as `.txt` files — pick a product, toggle one or more of its variants, get one file per variant.

**Architecture:** A read-only `ExportService` builds the data (which products/variants the user has delivered content for, and the per-order delivered lines). A pure `export_formatter` turns that data into file text. A new `export.py` handler module drives the multi-step, edit-in-place Telegram flow and sends the files via `send_document`. Entry points: `/export` command, a `/start` inline button, and a persistent reply-keyboard button.

**Tech Stack:** Python 3.11+, python-telegram-bot (async handlers, **synchronous** SQLAlchemy services), SQLAlchemy 2.0 `select()`, pytest with in-memory SQLite fixtures.

## Global Constraints

- **Privacy (load-bearing):** every query is scoped to the requesting user's `telegram_user_id` AND `Order.status == OrderStatus.DELIVERED` AND `PreUploadedProduct.is_used == True`. Never return another user's delivered content.
- **Pre-uploaded only:** exportable rows come exclusively from `pre_uploaded_products` joined through `used_by_order_id`. Supplier products are excluded structurally.
- **Sync DB layer:** services and queries are synchronous (no `await` on DB calls). Handlers are `async`. This matches existing code (`src/bot/handlers/refund.py`), not the CLAUDE.md "async services" note.
- **DB access only through a service:** all queries live in `ExportService`; handlers never query models directly.
- **Edit-in-place:** selection menus edit the existing message (`query.edit_message_text`). The generated `.txt` files are the one allowed exception — sent as new `send_document` messages.
- **i18n:** all user-facing strings and in-file labels go through `t()`; Vietnamese is default. No hardcoded strings.
- **Callbacks use list indices, not ids:** product/variant ids are opaque strings; callback data references the index into the state-stored list (`export_prod_<i>`, `export_var_<i>`) to avoid delimiter parsing bugs and the 64-byte callback limit.

## File Structure

- `src/database/services/export_service.py` *(new)* — data layer: 3 query methods + content renderer + two dataclasses.
- `src/bot/messages/export_formatter.py` *(new)* — pure file-text builder + filename slug.
- `src/bot/handlers/export.py` *(new)* — command + 6 callback handlers + keyboard builders.
- `src/bot/states/state_manager.py` *(modify)* — add export state fields to `UserState`.
- `src/bot/main.py` *(modify)* — register command + callback handlers.
- `src/bot/handlers/commands.py` *(modify)* — add `start_export` button to `_start_inline_keyboard`; route the reply-keyboard Export button in `handle_products_button`.
- `src/bot/utils/keyboard.py` *(modify)* — add Export button to the persistent keyboard.
- `src/i18n/locales/en/bot.json`, `src/i18n/locales/vi/bot.json` *(modify)* — `buttons.export` + `commands.export.*`.
- `tests/test_export_service.py`, `tests/test_export_formatter.py`, `tests/test_export_handler.py` *(new)*.

---

## Task 1: `ExportService` data layer

**Files:**
- Create: `src/database/services/export_service.py`
- Test: `tests/test_export_service.py`

**Interfaces:**
- Produces:
  - `ExportService(session)` with:
    - `get_exportable_products(user_id: int) -> list[dict]` → `[{"id": str, "name": str}, ...]` ordered by name.
    - `get_exportable_variations(user_id: int, product_id: str) -> list[dict]` → `[{"id", "name"}, ...]`.
    - `get_variant_export(user_id: int, product_id: str, variation_id: str) -> ExportVariantData | None`.
  - `ExportVariantData` dataclass: `product_id, product_name, variation_id, variation_name, orders: list[ExportOrderEntry]`; properties `total_orders: int`, `total_items: int`.
  - `ExportOrderEntry` dataclass: `order_id, created_at, price: int, quantity: int, bonus_quantity: int, contents: list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export_service.py`:

```python
"""Tests for the /export data service."""
import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.models.order import Order
from src.database.models.order_item import OrderItem
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.services.export_service import ExportService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed_delivered_order(session, *, order_id, user_id, product_id, variation_id,
                          subtotal, quantity, bonus, contents, created_at):
    """Create a DELIVERED order with one item and `len(contents)` used rows."""
    session.add(Order(id=order_id, user_id=user_id, status=OrderStatus.DELIVERED,
                       total_amount=subtotal, created_at=created_at))
    session.add(OrderItem(id=f"oi_{order_id}", order_id=order_id, product_id=product_id,
                          variation_id=variation_id, quantity=quantity, bonus_quantity=bonus,
                          unit_price=subtotal, subtotal=subtotal))
    for i, c in enumerate(contents):
        session.add(PreUploadedProduct(
            id=f"pu_{order_id}_{i}", product_id=product_id, variation_id=variation_id,
            product_data=c, is_used=True, used_by_order_id=order_id, used_at=created_at))
    session.commit()


@pytest.fixture
def seeded(db_session):
    s = db_session
    s.add(Product(id="p1", name="Netflix", delivery_type=DeliveryType.PRE_UPLOADED, is_active=True))
    s.add(Product(id="p2", name="Spotify", delivery_type=DeliveryType.PRE_UPLOADED, is_active=True))
    s.add(ProductVariation(id="v1", product_id="p1", name="1 Month", price=90000, stock=5))
    s.add(ProductVariation(id="v2", product_id="p1", name="12 Month", price=900000, stock=5))
    s.add(ProductVariation(id="v3", product_id="p2", name="Premium", price=50000, stock=5))
    s.commit()
    # User 100: two delivered orders of p1/v1, one of p1/v2, one of p2/v3.
    _seed_delivered_order(s, order_id="o1", user_id=100, product_id="p1", variation_id="v1",
                          subtotal=90000, quantity=1, bonus=0, contents=["acc1@mail|x"],
                          created_at=datetime(2026, 6, 1, 7, 30))
    _seed_delivered_order(s, order_id="o2", user_id=100, product_id="p1", variation_id="v1",
                          subtotal=270000, quantity=3, bonus=0,
                          contents=["acc2@mail|x", "acc3@mail|x", "acc4@mail|x"],
                          created_at=datetime(2026, 6, 10, 2, 12))
    _seed_delivered_order(s, order_id="o3", user_id=100, product_id="p1", variation_id="v2",
                          subtotal=900000, quantity=1, bonus=0, contents=["acc5@mail|x"],
                          created_at=datetime(2026, 6, 11, 0, 0))
    _seed_delivered_order(s, order_id="o4", user_id=100, product_id="p2", variation_id="v3",
                          subtotal=50000, quantity=1, bonus=0, contents=["acc6@mail|x"],
                          created_at=datetime(2026, 6, 12, 0, 0))
    # Another user's delivered order — MUST NEVER leak into user 100's export.
    _seed_delivered_order(s, order_id="o5", user_id=999, product_id="p1", variation_id="v1",
                          subtotal=90000, quantity=1, bonus=0, contents=["OTHERUSER@mail|x"],
                          created_at=datetime(2026, 6, 1, 0, 0))
    # A PAID-but-not-delivered order — MUST be excluded (status filter).
    s.add(Order(id="o6", user_id=100, status=OrderStatus.PAID, total_amount=90000,
                created_at=datetime(2026, 6, 13, 0, 0)))
    s.add(PreUploadedProduct(id="pu_o6_0", product_id="p1", variation_id="v1",
                             product_data="NOTDELIVERED@mail|x", is_used=False,
                             used_by_order_id="o6"))
    s.commit()
    return s


def test_exportable_products_are_distinct_and_user_scoped(seeded):
    svc = ExportService(seeded)
    products = svc.get_exportable_products(100)
    assert [p["name"] for p in products] == ["Netflix", "Spotify"]  # sorted, distinct
    ids = {p["id"] for p in products}
    assert ids == {"p1", "p2"}


def test_exportable_products_excludes_other_users(seeded):
    svc = ExportService(seeded)
    assert svc.get_exportable_products(999) == [{"id": "p1", "name": "Netflix"}]


def test_exportable_variations(seeded):
    svc = ExportService(seeded)
    variations = svc.get_exportable_variations(100, "p1")
    assert [v["name"] for v in variations] == ["1 Month", "12 Month"]


def test_variant_export_groups_orders_and_counts_items(seeded):
    svc = ExportService(seeded)
    data = svc.get_variant_export(100, "p1", "v1")
    assert data is not None
    assert data.product_name == "Netflix"
    assert data.variation_name == "1 Month"
    assert data.total_orders == 2          # o1 + o2
    assert data.total_items == 4           # 1 + 3 delivered rows
    o1, o2 = data.orders                    # ordered by created_at
    assert o1.order_id == "o1" and o1.contents == ["acc1@mail|x"]
    assert o2.order_id == "o2" and len(o2.contents) == 3
    assert o2.price == 270000 and o2.quantity == 3


def test_variant_export_does_not_leak_other_variant(seeded):
    svc = ExportService(seeded)
    data = svc.get_variant_export(100, "p1", "v1")
    flat = [c for o in data.orders for c in o.contents]
    assert "acc5@mail|x" not in flat        # that belongs to v2
    assert "OTHERUSER@mail|x" not in flat    # belongs to user 999
    assert "NOTDELIVERED@mail|x" not in flat # belongs to PAID order o6


def test_variant_export_none_when_empty(seeded):
    svc = ExportService(seeded)
    assert svc.get_variant_export(100, "p1", "nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_export_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.database.services.export_service'`

- [ ] **Step 3: Write the implementation**

Create `src/database/services/export_service.py`:

```python
"""
Read-only data service for the customer /export feature.

Builds what /export needs: which products/variants the requesting user has
delivered pre-uploaded content for, and the per-order delivered content lines.
Every query is scoped to the user's Telegram id, to DELIVERED orders, and to
used pre-uploaded rows — never return another user's delivered credentials.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models.enums import OrderStatus
from src.database.models.order import Order
from src.database.models.order_item import OrderItem
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation

logger = logging.getLogger(__name__)


@dataclass
class ExportOrderEntry:
    order_id: str
    created_at: datetime
    price: int            # OrderItem.subtotal for this variant in this order
    quantity: int         # OrderItem.quantity
    bonus_quantity: int   # OrderItem.bonus_quantity
    contents: list = field(default_factory=list)  # list[str] delivered content lines


@dataclass
class ExportVariantData:
    product_id: str
    product_name: str
    variation_id: str
    variation_name: str
    orders: list = field(default_factory=list)  # list[ExportOrderEntry]

    @property
    def total_orders(self) -> int:
        return len(self.orders)

    @property
    def total_items(self) -> int:
        return sum(len(o.contents) for o in self.orders)


def _render_delivery_content(raw_data: Optional[str]) -> str:
    """Render one PreUploadedProduct.product_data exactly the way the delivery
    flow shows it to the customer (mirrors src/ipn/processor.py)."""
    if not raw_data:
        return "[No delivery data available]"
    try:
        parsed = json.loads(raw_data)
    except (json.JSONDecodeError, TypeError):
        return raw_data  # plain text
    if isinstance(parsed, dict):
        if not parsed:
            return "[No delivery data available]"
        if "delivery_data" in parsed and len(parsed) == 1:
            return str(parsed["delivery_data"])
        if "value" in parsed and len(parsed) == 1:
            return str(parsed["value"])
        return "\n".join(f"{k}: {v}" for k, v in parsed.items())
    return str(parsed)  # JSON scalar


class ExportService:
    """Read-only queries for the /export feature."""

    def __init__(self, session: Session):
        self.session = session

    def get_exportable_products(self, user_id: int) -> list[dict]:
        rows = self.session.execute(
            select(Product.id, Product.name)
            .join(PreUploadedProduct, PreUploadedProduct.product_id == Product.id)
            .join(Order, Order.id == PreUploadedProduct.used_by_order_id)
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                PreUploadedProduct.is_used.is_(True),
            )
            .distinct()
            .order_by(Product.name)
        ).all()
        return [{"id": r[0], "name": r[1]} for r in rows]

    def get_exportable_variations(self, user_id: int, product_id: str) -> list[dict]:
        rows = self.session.execute(
            select(ProductVariation.id, ProductVariation.name)
            .join(PreUploadedProduct,
                  PreUploadedProduct.variation_id == ProductVariation.id)
            .join(Order, Order.id == PreUploadedProduct.used_by_order_id)
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                PreUploadedProduct.product_id == product_id,
                PreUploadedProduct.is_used.is_(True),
            )
            .distinct()
            .order_by(ProductVariation.name)
        ).all()
        return [{"id": r[0], "name": r[1]} for r in rows]

    def get_variant_export(
        self, user_id: int, product_id: str, variation_id: str
    ) -> Optional[ExportVariantData]:
        product = self.session.get(Product, product_id)
        variation = self.session.get(ProductVariation, variation_id)
        if product is None or variation is None:
            return None

        rows = self.session.execute(
            select(PreUploadedProduct, Order)
            .join(Order, Order.id == PreUploadedProduct.used_by_order_id)
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.DELIVERED,
                PreUploadedProduct.product_id == product_id,
                PreUploadedProduct.variation_id == variation_id,
                PreUploadedProduct.is_used.is_(True),
            )
            .order_by(Order.created_at, PreUploadedProduct.used_at)
        ).all()
        if not rows:
            return None

        by_order: dict[str, ExportOrderEntry] = {}
        for pre, order in rows:
            entry = by_order.get(order.id)
            if entry is None:
                item = self.session.execute(
                    select(OrderItem).where(
                        OrderItem.order_id == order.id,
                        OrderItem.product_id == product_id,
                        OrderItem.variation_id == variation_id,
                    )
                ).scalars().first()
                entry = ExportOrderEntry(
                    order_id=order.id,
                    created_at=order.created_at,
                    price=item.subtotal if item else 0,
                    quantity=item.quantity if item else 0,
                    bonus_quantity=item.bonus_quantity if item else 0,
                    contents=[],
                )
                by_order[order.id] = entry
            entry.contents.append(_render_delivery_content(pre.product_data))

        return ExportVariantData(
            product_id=product_id,
            product_name=product.name,
            variation_id=variation_id,
            variation_name=variation.name,
            orders=list(by_order.values()),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_export_service.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/database/services/export_service.py tests/test_export_service.py
git commit -m "feat(export): add read-only ExportService data layer"
```

---

## Task 2: `export_formatter` — file text builder

**Files:**
- Create: `src/bot/messages/export_formatter.py`
- Test: `tests/test_export_formatter.py`

**Interfaces:**
- Consumes: `ExportVariantData`, `ExportOrderEntry` from Task 1.
- Produces:
  - `slugify_filename(text: str, fallback: str) -> str`
  - `build_variant_file(data: ExportVariantData, labels: dict, tz) -> tuple[str, str]` → `(filename, content)`. `labels` keys: `totals, order, date, price, qty, delivered, vnd`. `tz` is a `ZoneInfo`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export_formatter.py`:

```python
"""Tests for the /export file-text builder."""
from datetime import datetime

from src.bot.messages.export_formatter import build_variant_file, slugify_filename
from src.database.services.export_service import ExportOrderEntry, ExportVariantData
from src.utils.datetime_format import resolve_tz

# English label templates (exactly what t() returns with no kwargs applied).
LABELS = {
    "totals": "Total orders: {orders} | Total items: {items}",
    "order": "--- Order {order_id} ---",
    "date": "Date:",
    "price": "Price:",
    "qty": "Qty:",
    "delivered": "Delivered:",
    "vnd": "VND",
}
TZ = resolve_tz("UTC")


def _sample():
    return ExportVariantData(
        product_id="p1", product_name="Netflix",
        variation_id="v1", variation_name="1 Month",
        orders=[
            ExportOrderEntry("o1", datetime(2026, 6, 1, 14, 30), 90000, 1, 0, ["acc1@mail|x"]),
            ExportOrderEntry("o2", datetime(2026, 6, 10, 9, 12), 270000, 3, 0,
                             ["acc2@mail|x", "acc3@mail|x", "acc4@mail|x"]),
        ],
    )


def test_slugify_filename():
    assert slugify_filename("Netflix Premium", "fb") == "Netflix_Premium"
    assert slugify_filename("12 Month / 1PCS", "fb") == "12_Month_1PCS"
    assert slugify_filename("", "fallback123") == "fallback123"
    assert slugify_filename("???", "fb") == "fb"


def test_build_variant_file_filename():
    fn, _ = build_variant_file(_sample(), LABELS, TZ)
    assert fn == "export_Netflix_1_Month.txt"


def test_build_variant_file_header_and_totals():
    _, content = build_variant_file(_sample(), LABELS, TZ)
    assert content.startswith("=== Netflix / 1 Month ===\n")
    assert "Total orders: 2 | Total items: 4" in content


def test_build_variant_file_order_blocks():
    _, content = build_variant_file(_sample(), LABELS, TZ)
    assert "--- Order o1 ---" in content
    assert "Date: 2026-06-01 14:30" in content
    assert "Price: 90.000 VND  Qty: 1" in content   # VND uses dot separators
    assert "Delivered:" in content
    assert "  acc1@mail|x" in content
    assert "  acc4@mail|x" in content


def test_build_variant_file_counts_bonus_in_qty():
    data = ExportVariantData("p1", "Netflix", "v1", "1 Month",
        orders=[ExportOrderEntry("o9", datetime(2026, 6, 1, 0, 0), 90000, 2, 1, ["a", "b", "c"])])
    _, content = build_variant_file(data, LABELS, TZ)
    assert "Qty: 3" in content   # quantity 2 + bonus 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_export_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.bot.messages.export_formatter'`

- [ ] **Step 3: Write the implementation**

Create `src/bot/messages/export_formatter.py`:

```python
"""
Pure text builders for the /export feature — no DB, no Telegram, easily tested.
"""
import re

from src.database.services.export_service import ExportVariantData
from src.utils.datetime_format import format_local


def slugify_filename(text: str, fallback: str) -> str:
    """ASCII-safe filename fragment; falls back when the result is empty."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")
    return slug or fallback


def build_variant_file(data: ExportVariantData, labels: dict, tz) -> tuple[str, str]:
    """Build (filename, file_content) for one product+variant.

    labels keys: totals, order, date, price, qty, delivered, vnd
    tz: ZoneInfo (from resolve_tz).
    """
    filename = "export_{}_{}.txt".format(
        slugify_filename(data.product_name, data.product_id),
        slugify_filename(data.variation_name, data.variation_id),
    )

    lines = [
        "=== {} / {} ===".format(data.product_name, data.variation_name),
        labels["totals"].format(orders=data.total_orders, items=data.total_items),
        "",
    ]
    for entry in data.orders:
        price_fmt = "{:,}".format(entry.price).replace(",", ".")
        qty = entry.quantity + entry.bonus_quantity
        date_str = format_local(entry.created_at, tz, "%Y-%m-%d %H:%M")
        lines.append(labels["order"].format(order_id=entry.order_id))
        lines.append("{} {}".format(labels["date"], date_str))
        lines.append(
            "{} {} {}  {} {}".format(
                labels["price"], price_fmt, labels["vnd"], labels["qty"], qty
            )
        )
        lines.append(labels["delivered"])
        for content in entry.contents:
            for content_line in (content.splitlines() or [content]):
                lines.append("  {}".format(content_line))
        lines.append("")

    return filename, "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_export_formatter.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/bot/messages/export_formatter.py tests/test_export_formatter.py
git commit -m "feat(export): add export file-text formatter"
```

---

## Task 3: i18n strings (vi + en)

**Files:**
- Modify: `src/i18n/locales/en/bot.json`
- Modify: `src/i18n/locales/vi/bot.json`

**Interfaces:**
- Produces translation keys consumed by Tasks 5–6: `buttons.export`, and `commands.export.{choose_product, choose_variants, export_button, empty, expired, none_selected, cancelled, done, file_totals, file_order, file_date, file_price, file_qty, file_delivered, file_vnd}`.

> Note: `file_totals` and `file_order` contain `{...}` placeholders. They are fetched with `t(key, update)` **without** kwargs (so `t()` returns the raw template) and `.format()`-ed inside `export_formatter`. The other `file_*` keys have no placeholders. `choose_variants` (`{product}`) and `done` (`{count}`) ARE passed kwargs through `t()`.

- [ ] **Step 1: Add `buttons.export` and `commands.export.*` to English**

In `src/i18n/locales/en/bot.json`, add `"export": "📤 Export"` to the `buttons` object, and add this block to the `commands` object:

```json
    "export": {
      "choose_product": "📤 Select a product to export your purchased data:",
      "choose_variants": "📦 {product}\nSelect one or more variants, then tap Export:",
      "export_button": "📤 Export selected",
      "empty": "You have no delivered purchases to export yet.",
      "expired": "This export session has expired. Please run /export again.",
      "none_selected": "Please select at least one variant first.",
      "cancelled": "Export cancelled.",
      "done": "✅ Exported {count} file(s).",
      "file_totals": "Total orders: {orders} | Total items: {items}",
      "file_order": "--- Order {order_id} ---",
      "file_date": "Date:",
      "file_price": "Price:",
      "file_qty": "Qty:",
      "file_delivered": "Delivered:",
      "file_vnd": "VND"
    }
```

- [ ] **Step 2: Add the same keys to Vietnamese**

In `src/i18n/locales/vi/bot.json`, add `"export": "📤 Xuất dữ liệu"` to the `buttons` object, and add this block to the `commands` object:

```json
    "export": {
      "choose_product": "📤 Chọn sản phẩm để xuất dữ liệu đã mua:",
      "choose_variants": "📦 {product}\nChọn một hoặc nhiều phân loại, rồi bấm Xuất:",
      "export_button": "📤 Xuất mục đã chọn",
      "empty": "Bạn chưa có đơn hàng đã giao nào để xuất.",
      "expired": "Phiên xuất dữ liệu đã hết hạn. Vui lòng dùng lại /export.",
      "none_selected": "Vui lòng chọn ít nhất một phân loại.",
      "cancelled": "Đã huỷ xuất dữ liệu.",
      "done": "✅ Đã xuất {count} tệp.",
      "file_totals": "Tổng đơn: {orders} | Tổng sản phẩm: {items}",
      "file_order": "--- Đơn {order_id} ---",
      "file_date": "Ngày:",
      "file_price": "Giá:",
      "file_qty": "SL:",
      "file_delivered": "Dữ liệu đã giao:",
      "file_vnd": "VND"
    }
```

- [ ] **Step 3: Verify both files are valid JSON and keys resolve**

Run:
```bash
python3 -c "import json; json.load(open('src/i18n/locales/en/bot.json')); json.load(open('src/i18n/locales/vi/bot.json')); print('JSON OK')"
python3 -c "from src.i18n.bot_translations import get_translation as g; print(g('buttons.export','vi')); print(g('commands.export.done','en',count=2)); print(g('commands.export.file_totals','en'))"
```
Expected: `JSON OK`, then `📤 Xuất dữ liệu`, `✅ Exported 2 file(s).`, and the raw `Total orders: {orders} | Total items: {items}` (un-formatted because no kwargs).

- [ ] **Step 4: Commit**

```bash
git add src/i18n/locales/en/bot.json src/i18n/locales/vi/bot.json
git commit -m "feat(export): add export i18n strings (vi + en)"
```

---

## Task 4: `UserState` export fields

**Files:**
- Modify: `src/bot/states/state_manager.py:8-30`
- Test: `tests/test_export_state.py`

**Interfaces:**
- Produces new `UserState` fields used by Task 5:
  - `export_products: list` (default `[]`)
  - `export_product_id: Optional[str]` (default `None`)
  - `export_variations: list` (default `[]`)
  - `export_selected_variation_ids: set` (default `set()`)

> The export handler mutates these directly via `get_user_state` / `set_user_state` (toggling a set does not fit the `update_user_state` None-guard pattern), so `update_user_state` is **not** changed.

- [ ] **Step 1: Write the failing test**

Create `tests/test_export_state.py`:

```python
"""Export-specific UserState fields."""
from src.bot.states.state_manager import StateManager, UserState


def test_userstate_export_defaults():
    st = UserState()
    assert st.export_products == []
    assert st.export_product_id is None
    assert st.export_variations == []
    assert st.export_selected_variation_ids == set()


def test_userstate_export_sets_are_independent():
    a, b = UserState(), UserState()
    a.export_selected_variation_ids.add("v1")
    assert b.export_selected_variation_ids == set()   # no shared mutable default


def test_set_and_get_roundtrip():
    mgr = StateManager()
    st = UserState()
    st.export_product_id = "p1"
    st.export_selected_variation_ids = {"v1", "v2"}
    mgr.set_user_state(42, st)
    got = mgr.get_user_state(42)
    assert got.export_product_id == "p1"
    assert got.export_selected_variation_ids == {"v1", "v2"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_state.py -v`
Expected: FAIL — `AttributeError: 'UserState' object has no attribute 'export_products'`

- [ ] **Step 3: Add the fields**

In `src/bot/states/state_manager.py`, the `UserState` dataclass already imports `field` (line 4: `from dataclasses import dataclass, field`). Add these lines at the end of the `UserState` dataclass body (after `balance_message_id` on line 29):

```python

    # /export flow state
    export_products: list = field(default_factory=list)  # [{"id","name"}] shown
    export_product_id: Optional[str] = None              # product chosen in step 1
    export_variations: list = field(default_factory=list)  # [{"id","name"}] of that product
    export_selected_variation_ids: set = field(default_factory=set)  # toggled variants
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_state.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/bot/states/state_manager.py tests/test_export_state.py
git commit -m "feat(export): add export flow fields to UserState"
```

---

## Task 5: Export handler module

**Files:**
- Create: `src/bot/handlers/export.py`
- Test: `tests/test_export_handler.py`

**Interfaces:**
- Consumes: `ExportService` (Task 1), `build_variant_file` (Task 2), `UserState` export fields (Task 4), `commands.export.*` i18n (Task 3), and the shared `state_manager` instance from `src/bot/handlers/commands.py`.
- Produces (registered by Task 6):
  - `export_command(update, context)` — `/export`
  - `handle_export_start(update, context)` — callback `^start_export$`
  - `handle_export_product(update, context)` — callback `^export_prod_`
  - `handle_export_variant_toggle(update, context)` — callback `^export_var_`
  - `handle_export_back(update, context)` — callback `^export_back$`
  - `handle_export_cancel(update, context)` — callback `^export_cancel$`
  - `handle_export_generate(update, context)` — callback `^export_go$`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export_handler.py`:

```python
"""Tests for the /export Telegram handlers (logic via mocks)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.bot.handlers.export as export
from src.bot.handlers.commands import state_manager
from src.bot.states.state_manager import UserState


@pytest.fixture(autouse=True)
def clear_state():
    state_manager._states.clear()
    yield
    state_manager._states.clear()


def _callback_update(user_id=100, data="export_go"):
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.from_user.id = user_id
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_user.id = user_id
    return update


@pytest.mark.asyncio
async def test_start_with_no_products_shows_empty_message():
    update = _callback_update(data="start_export")
    with patch.object(export, "get_session_factory") as gsf, \
         patch.object(export.ExportService, "get_exportable_products", return_value=[]):
        gsf.return_value.return_value = MagicMock()  # session
        await export.handle_export_start(update, MagicMock())
    update.callback_query.edit_message_text.assert_awaited()
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "no delivered" in text.lower() or "chưa có" in text.lower()


@pytest.mark.asyncio
async def test_start_with_products_stores_state_and_lists():
    update = _callback_update(data="start_export")
    products = [{"id": "p1", "name": "Netflix"}, {"id": "p2", "name": "Spotify"}]
    with patch.object(export, "get_session_factory") as gsf, \
         patch.object(export.ExportService, "get_exportable_products", return_value=products):
        gsf.return_value.return_value = MagicMock()
        await export.handle_export_start(update, MagicMock())
    st = state_manager.get_user_state(100)
    assert st.export_products == products
    kb = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    # one button per product + a cancel row
    assert len(kb.inline_keyboard) == 3


@pytest.mark.asyncio
async def test_variant_toggle_flips_selection():
    st = UserState()
    st.export_product_id = "p1"
    st.export_products = [{"id": "p1", "name": "Netflix"}]
    st.export_variations = [{"id": "v1", "name": "1 Month"}, {"id": "v2", "name": "12 Month"}]
    state_manager.set_user_state(100, st)

    update = _callback_update(data="export_var_0")
    await export.handle_export_variant_toggle(update, MagicMock())
    assert state_manager.get_user_state(100).export_selected_variation_ids == {"v1"}

    update2 = _callback_update(data="export_var_0")
    await export.handle_export_variant_toggle(update2, MagicMock())
    assert state_manager.get_user_state(100).export_selected_variation_ids == set()


@pytest.mark.asyncio
async def test_generate_with_nothing_selected_alerts():
    st = UserState()
    st.export_product_id = "p1"
    st.export_selected_variation_ids = set()
    state_manager.set_user_state(100, st)

    update = _callback_update(data="export_go")
    await export.handle_export_generate(update, MagicMock())
    update.callback_query.answer.assert_awaited()
    assert update.callback_query.answer.call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_cancel_clears_state():
    state_manager.set_user_state(100, UserState())
    update = _callback_update(data="export_cancel")
    await export.handle_export_cancel(update, MagicMock())
    assert state_manager.get_user_state(100) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_export_handler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.bot.handlers.export'`

- [ ] **Step 3: Write the implementation**

Create `src/bot/handlers/export.py`:

```python
"""
Customer /export flow.

Pick a product, toggle one or more of its variants, then receive one .txt per
variant containing every delivered pre-uploaded order for that product+variant.
Selection menus edit in place; the .txt files are sent as new documents.
"""
import logging
from io import BytesIO

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot.handlers.commands import state_manager
from src.bot.messages.export_formatter import build_variant_file
from src.bot.states.state_manager import UserState
from src.bot.utils.language import t
from src.database.connection import get_session_factory
from src.database.services.app_settings_service import AppSettingsService
from src.database.services.export_service import ExportService
from src.utils.datetime_format import resolve_tz

logger = logging.getLogger(__name__)


def _export_labels(update: Update) -> dict:
    """Resolve the in-file labels (no kwargs → templates returned raw)."""
    return {
        "totals": t("commands.export.file_totals", update),
        "order": t("commands.export.file_order", update),
        "date": t("commands.export.file_date", update),
        "price": t("commands.export.file_price", update),
        "qty": t("commands.export.file_qty", update),
        "delivered": t("commands.export.file_delivered", update),
        "vnd": t("commands.export.file_vnd", update),
    }


def _product_list_keyboard(products: list, update: Update) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(p["name"], callback_data=f"export_prod_{i}")]
        for i, p in enumerate(products)
    ]
    rows.append([InlineKeyboardButton(t("buttons.cancel", update),
                                      callback_data="export_cancel")])
    return InlineKeyboardMarkup(rows)


def _variant_keyboard(variations: list, selected: set, update: Update) -> InlineKeyboardMarkup:
    rows = []
    for i, v in enumerate(variations):
        mark = "✅ " if v["id"] in selected else "▫️ "
        rows.append([InlineKeyboardButton(f"{mark}{v['name']}",
                                          callback_data=f"export_var_{i}")])
    rows.append([InlineKeyboardButton(t("commands.export.export_button", update),
                                      callback_data="export_go")])
    rows.append([
        InlineKeyboardButton(t("buttons.back", update), callback_data="export_back"),
        InlineKeyboardButton(t("buttons.cancel", update), callback_data="export_cancel"),
    ])
    return InlineKeyboardMarkup(rows)


async def _render_product_list(update: Update, user_id: int, *, edit: bool) -> None:
    session = get_session_factory()()
    try:
        products = ExportService(session).get_exportable_products(user_id)
    finally:
        session.close()

    if not products:
        text = t("commands.export.empty", update)
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        state_manager.clear_user_state(user_id)
        return

    state = state_manager.get_user_state(user_id) or UserState()
    state.export_products = products
    state.export_product_id = None
    state.export_variations = []
    state.export_selected_variation_ids = set()
    state_manager.set_user_state(user_id, state)

    text = t("commands.export.choose_product", update)
    kb = _product_list_keyboard(products, update)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/export entry point."""
    if not update.message:
        return
    await _render_product_list(update, update.effective_user.id, edit=False)


async def handle_export_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback start_export — from the /start inline menu."""
    query = update.callback_query
    await query.answer()
    await _render_product_list(update, query.from_user.id, edit=True)


async def handle_export_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_prod_<idx> — show variant multi-select."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = state_manager.get_user_state(user_id)
    if not state or not state.export_products:
        await query.edit_message_text(t("commands.export.expired", update))
        return
    try:
        idx = int((query.data or "").rsplit("_", 1)[1])
        product = state.export_products[idx]
    except (ValueError, IndexError):
        await query.edit_message_text(t("commands.export.expired", update))
        return

    session = get_session_factory()()
    try:
        variations = ExportService(session).get_exportable_variations(user_id, product["id"])
    finally:
        session.close()

    state.export_product_id = product["id"]
    state.export_variations = variations
    state.export_selected_variation_ids = set()
    state_manager.set_user_state(user_id, state)

    text = t("commands.export.choose_variants", update, product=product["name"])
    await query.edit_message_text(text, reply_markup=_variant_keyboard(variations, set(), update))


async def handle_export_variant_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_var_<idx> — toggle a variant selection in place."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = state_manager.get_user_state(user_id)
    if not state or not state.export_variations:
        await query.edit_message_text(t("commands.export.expired", update))
        return
    try:
        idx = int((query.data or "").rsplit("_", 1)[1])
        var_id = state.export_variations[idx]["id"]
    except (ValueError, IndexError):
        await query.edit_message_text(t("commands.export.expired", update))
        return

    selected = set(state.export_selected_variation_ids)
    selected ^= {var_id}
    state.export_selected_variation_ids = selected
    state_manager.set_user_state(user_id, state)

    product_name = next(
        (p["name"] for p in state.export_products if p["id"] == state.export_product_id), ""
    )
    text = t("commands.export.choose_variants", update, product=product_name)
    await query.edit_message_text(
        text, reply_markup=_variant_keyboard(state.export_variations, selected, update)
    )


async def handle_export_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_back — return to the product list."""
    query = update.callback_query
    await query.answer()
    await _render_product_list(update, query.from_user.id, edit=True)


async def handle_export_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_cancel — clear state and close."""
    query = update.callback_query
    await query.answer()
    state_manager.clear_user_state(query.from_user.id)
    await query.edit_message_text(t("commands.export.cancelled", update))


async def handle_export_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_go — build and send one .txt per selected variant."""
    query = update.callback_query
    user_id = query.from_user.id
    state = state_manager.get_user_state(user_id)
    if not state or not state.export_product_id or not state.export_selected_variation_ids:
        # Answer with an alert (do NOT answer() before this branch).
        await query.answer(t("commands.export.none_selected", update), show_alert=True)
        return
    await query.answer()

    labels = _export_labels(update)
    product_id = state.export_product_id
    selected = list(state.export_selected_variation_ids)

    session = get_session_factory()()
    sent = 0
    try:
        service = ExportService(session)
        tz = resolve_tz(AppSettingsService(session).get_settings().timezone)
        for variation_id in selected:
            data = service.get_variant_export(user_id, product_id, variation_id)
            if data is None:
                continue
            filename, content = build_variant_file(data, labels, tz)
            file_obj = BytesIO(content.encode("utf-8"))
            file_obj.name = filename
            try:
                await context.bot.send_document(
                    chat_id=user_id, document=file_obj, filename=filename
                )
                sent += 1
            except Exception as e:
                logger.error(f"Export send_document failed for {filename}: {e}", exc_info=True)
    finally:
        session.close()

    state_manager.clear_user_state(user_id)
    await query.edit_message_text(t("commands.export.done", update, count=sent))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_export_handler.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/bot/handlers/export.py tests/test_export_handler.py
git commit -m "feat(export): add /export flow handlers"
```

---

## Task 6: Wiring — register handlers, menu button, reply keyboard

**Files:**
- Modify: `src/bot/main.py:69-73` (imports) and `:120` / `:181-190` (registration)
- Modify: `src/bot/handlers/commands.py:76-87` (`_start_inline_keyboard`) and `:450-505` (`handle_products_button`)
- Modify: `src/bot/utils/keyboard.py:25-29`
- Test: `tests/test_export_wiring.py`

**Interfaces:**
- Consumes the handlers exported by Task 5 and `buttons.export` from Task 3.

- [ ] **Step 1: Write the failing test**

Create `tests/test_export_wiring.py`:

```python
"""Verify /export handlers and buttons are wired in."""
from unittest.mock import MagicMock

from telegram.ext import CommandHandler

from src.bot.handlers.commands import _start_inline_keyboard
from src.bot.utils.keyboard import get_persistent_keyboard


def _fake_update():
    u = MagicMock()
    u.effective_user.language_code = "en"
    return u


def test_start_command_registered():
    import src.bot.main as main
    app = main.create_bot_application.__wrapped__ if hasattr(
        main.create_bot_application, "__wrapped__") else None
    # Build directly; requires TELEGRAM_BOT_TOKEN — skip if missing.


def test_export_button_in_start_inline_keyboard():
    kb = _start_inline_keyboard(_fake_update())
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "start_export" in datas


def test_export_button_in_persistent_keyboard():
    kb = get_persistent_keyboard(_fake_update())
    texts = [b.text for row in kb.keyboard for b in row]
    assert any("Export" in t or "Xuất" in t for t in texts)
```

> Drop the placeholder `test_start_command_registered` body and instead assert registration through the handler list — see Step 5's verification command, which is the reliable check. Keep only the two keyboard tests in this file.

Replace the file content with just:

```python
"""Verify /export buttons are wired into the keyboards."""
from unittest.mock import MagicMock

from src.bot.handlers.commands import _start_inline_keyboard
from src.bot.utils.keyboard import get_persistent_keyboard


def _fake_update():
    u = MagicMock()
    u.effective_user.language_code = "en"
    return u


def test_export_button_in_start_inline_keyboard():
    kb = _start_inline_keyboard(_fake_update())
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "start_export" in datas


def test_export_button_in_persistent_keyboard():
    kb = get_persistent_keyboard(_fake_update())
    texts = [b.text for row in kb.keyboard for b in row]
    assert any(("Export" in txt) or ("Xuất" in txt) for txt in texts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_wiring.py -v`
Expected: FAIL — `assert 'start_export' in [...]` (button not present yet)

- [ ] **Step 3: Add the inline `/start` button**

In `src/bot/handlers/commands.py`, change `_start_inline_keyboard` (lines 76-87) to add a third row:

```python
def _start_inline_keyboard(update: Update) -> InlineKeyboardMarkup:
    """Build the start menu inline keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("buttons.products", update), callback_data="start_products"),
            InlineKeyboardButton(t("buttons.balance", update), callback_data="balance_view"),
        ],
        [
            InlineKeyboardButton(t("buttons.order_history", update), callback_data="start_history"),
            InlineKeyboardButton(t("start_menu.api_button", update), callback_data="start_api"),
        ],
        [
            InlineKeyboardButton(t("buttons.export", update), callback_data="start_export"),
        ],
    ])
```

- [ ] **Step 4: Add the persistent reply-keyboard button + route it**

In `src/bot/utils/keyboard.py`, add the export button text and a row (replace lines 18-29):

```python
    products_text = t("buttons.products", update)
    order_history_text = t("buttons.order_history", update)
    balance_text = t("buttons.balance", update)
    language_text = t("buttons.language", update)
    top_buyers_text = t("buttons.top_buyers", update)
    api_text = t("start_menu.api_button", update)
    export_text = t("buttons.export", update)

    keyboard = [
        [KeyboardButton(products_text), KeyboardButton(order_history_text)],
        [KeyboardButton(balance_text), KeyboardButton(top_buyers_text)],
        [KeyboardButton(api_text), KeyboardButton(language_text)],
        [KeyboardButton(export_text)],
    ]
```

In `src/bot/handlers/commands.py` `handle_products_button` (after the `api_variations` block, before the closing of the function ~line 505), add:

```python
    export_text = t("buttons.export", update)
    export_variations = {export_text, "📤 Export", "📤 Xuất dữ liệu"}
    if message_text in export_variations:
        from src.bot.handlers.export import export_command
        await export_command(update, context)
        return
```

(The local import avoids a circular import, matching the existing balance/api routing pattern.)

- [ ] **Step 5: Register command + callback handlers in `main.py`**

In `src/bot/main.py`, add to the import block (after the refund import, lines 69-73):

```python
from src.bot.handlers.export import (
    export_command,
    handle_export_start,
    handle_export_product,
    handle_export_variant_toggle,
    handle_export_back,
    handle_export_cancel,
    handle_export_generate,
)
```

Add the command handler after line 120 (`CommandHandler("rf", refund_command)`):

```python
    application.add_handler(CommandHandler("export", export_command))
```

Add the callback handlers near the other start-menu callbacks (after the `start_api` block, ~line 200). **Order matters:** register the more specific `export_prod_` / `export_var_` prefixes; the `$`-anchored ones are unambiguous:

```python
    # /export flow callbacks
    application.add_handler(
        CallbackQueryHandler(handle_export_start, pattern="^start_export$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_product, pattern="^export_prod_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_variant_toggle, pattern="^export_var_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_generate, pattern="^export_go$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_back, pattern="^export_back$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_cancel, pattern="^export_cancel$")
    )
```

- [ ] **Step 6: Run the wiring test + import smoke check**

Run:
```bash
pytest tests/test_export_wiring.py -v
python3 -c "import src.bot.main; import src.bot.handlers.export; print('imports OK (no circular import)')"
```
Expected: 2 passed; `imports OK (no circular import)`

- [ ] **Step 7: Full test suite + lint**

Run:
```bash
pytest tests/test_export_service.py tests/test_export_formatter.py tests/test_export_state.py tests/test_export_handler.py tests/test_export_wiring.py -v
ruff check src/bot/handlers/export.py src/bot/messages/export_formatter.py src/database/services/export_service.py
```
Expected: all export tests pass; ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/bot/main.py src/bot/handlers/commands.py src/bot/utils/keyboard.py tests/test_export_wiring.py
git commit -m "feat(export): wire /export command, start-menu button, and reply keyboard"
```

---

## Manual Verification (after Task 6)

Run the customer bot (`python -m src.bot.main`) against a DB that has a user with at least one DELIVERED pre-uploaded order across two variants, then:

1. `/start` → confirm the **📤 Export** inline button and the reply-keyboard button appear.
2. Tap **Export** (or `/export`) → product list shows only products with delivered pre-uploaded purchases.
3. Pick a product → variant list shows `▫️`/`✅` toggles; toggle two variants.
4. Tap **Export selected** → receive two `.txt` files; open each and confirm: header `=== Product / Variant ===`, correct totals, one block per order with date (app timezone), price (dot separators) + VND, qty incl. bonus, and the delivered content lines — and that **no other variant's or user's content** appears.
5. With nothing selected, tap Export → inline alert "select at least one variant".
6. **Back** returns to the product list; **Cancel** closes with the cancelled message.
7. A user with no delivered pre-uploaded orders → `/export` shows the empty-state message.

---

## Self-Review (completed during planning)

- **Spec coverage:** entry points (T6), product→variant→export flow (T5), pre-uploaded+DELIVERED+user-scoped queries (T1), per-variant attribution join (T1), file format incl. bonus-aware item count (T2), dedicated ExportService (T1), i18n incl. in-file labels (T3), state (T4), empty/no-selection/send-failure handling (T1/T5). All covered.
- **Placeholder scan:** the one placeholder test stub in T6 Step 1 is explicitly flagged and replaced inline with the final two-test file.
- **Type consistency:** `ExportVariantData` / `ExportOrderEntry` field names and the `labels` dict keys (`totals, order, date, price, qty, delivered, vnd`) match between T1, T2, and T5; callback patterns in T6 match the handler names/prefixes in T5.
