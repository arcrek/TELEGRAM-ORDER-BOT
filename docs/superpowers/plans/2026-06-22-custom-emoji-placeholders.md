# Custom Emoji Placeholders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins use Telegram premium/custom emoji throughout the bot (product list/detail, admin notifications, customer order messages) via reusable named placeholders referenced with a `{emo:<id>}` token.

**Architecture:** A new `emoji_placeholders` table stores each placeholder's captured content (an ordered list of custom-emoji + text units). Admins create a placeholder in the dashboard (gets a numeric id), then run `/set_emo <id>` in the bot and send the premium emoji — the bot reads each `custom_emoji_id` off the message entities and saves it. Authors embed `{emo:<id>}` tokens in any text field. At send time a central renderer HTML-escapes the human text, substitutes tokens with `<tg-emoji>` HTML, and sends with `parse_mode=HTML`. A message only switches to HTML when it actually contains a token, so existing plain-text messages are unchanged.

**Tech Stack:** python-telegram-bot ≥22.7, SQLAlchemy 2.0, Alembic, FastAPI, React 18 + TypeScript (Vite, axios, vitest), PostgreSQL (SQLite in tests).

## Global Constraints

- Python 3.11+; bot DB service layer is **synchronous** (`__init__(self, session: Session)`, queries on `self.session`, explicit `self.session.commit()`).
- All DB schema changes require an Alembic migration; never modify tables directly. Current Alembic head: `h8c9d0e1f2a3`.
- DB access only through `src/database/services/`; never raw queries in handlers/routers.
- All bot handlers and dashboard endpoints are `async`; type-hint everything; use Pydantic for API schemas.
- Custom emoji render ONLY via `parse_mode="HTML"` with `<tg-emoji emoji-id="ID">fallback</tg-emoji>`. Human/dynamic content MUST be HTML-escaped BEFORE token substitution.
- Tests use in-memory SQLite (`sqlalchemy.create_engine("sqlite://")` + `Base.metadata.create_all`).
- Frontend API calls go through `apiClient` (`frontend/src/shared/lib/api.ts`); errors via `formatApiError`.
- Commit after every task. Branch: `feat/custom-emoji-placeholders` (already created).

---

## File Structure

**Backend — create:**
- `src/database/models/emoji_placeholder.py` — `EmojiPlaceholder` model
- `src/database/services/emoji_placeholder_service.py` — CRUD + `units_to_html` + `get_rendered_html` (cache)
- `src/bot/messages/emoji_renderer.py` — `parse_emoji_units` (capture) + `render` (token→HTML)
- `src/bot/handlers/emoji_admin.py` — `/set_emo` command + follow-up message handler
- `src/dashboard/routers/emoji_placeholders.py` — dashboard CRUD API
- `src/database/migrations/versions/i9d0e1f2a3b4_add_emoji_placeholders.py` — migration
- `tests/test_emoji_renderer.py`, `tests/test_emoji_placeholder_service.py`, `tests/test_notification_emoji.py`

**Backend — modify:**
- `src/database/models/notification_settings.py` — add `header_placeholder_id`, `footer_placeholder_id`
- `src/database/services/notification_settings_service.py` — persist the two new fields
- `src/database/services/order_notification_service.py` — compose header/footer + render before send
- `src/bot/states/state_manager.py` — add `awaiting_emoji_input`, `pending_emoji_placeholder_id`
- `src/bot/main.py` — register command + message handler
- `src/bot/handlers/callbacks.py` — render product detail/list before sending
- `src/dashboard/main.py` — mount new router
- `src/dashboard/routers/notifications.py` — add the two fields to schemas + endpoints

**Frontend — create:**
- `frontend/src/pages/EmojiPlaceholdersPage.tsx`

**Frontend — modify:**
- `frontend/src/app/routes.ts` — nav entry
- `frontend/src/App.tsx` — route
- `frontend/src/app/layouts/Sidebar.tsx` — ensure icon mapped
- `frontend/src/pages/NotificationsPage.tsx` — header/footer dropdowns
- locale JSON (`frontend/src/**/locales` or i18n resource) — `nav.emojiPlaceholders` + page labels

---

### Task 0: Spike — prove the foundation (GATES ALL OTHER TASKS)

**Why:** The entire feature rests on "the Premium bot owner lets the bot *send* custom emoji." That came from community discussions, not a confirmed primary source, and the official-docs check was inconclusive (the documented path is historically the Fragment username purchase). A ~10-minute empirical test gates days of work. **Do not start Task 1 until this passes.**

This spike is throwaway code (a scratch branch or a temporary handler) — not committed to the feature.

- [ ] **Step 1: Capture a real custom_emoji_id**

Add a temporary handler (or use an existing debug path) that logs incoming entities:

```python
async def _spike(update, context):
    msg = update.message
    print("TEXT:", repr(msg.text))
    for e in (msg.entities or []):
        print("ENTITY:", e.type, e.offset, e.length, getattr(e, "custom_emoji_id", None))
```

Have the **Premium owner account** DM the bot a premium/animated emoji. Confirm a `custom_emoji` entity with a non-null `custom_emoji_id` is logged. (This also validates the capture mechanism for Task 3/5 for free.)

- [ ] **Step 2: Echo it back in a PRIVATE chat**

```python
await update.message.reply_text(
    '<tg-emoji emoji-id="PASTE_ID">🔥</tg-emoji>', parse_mode="HTML"
)
```

Expected: the premium emoji renders. A `telegram.error.BadRequest` (e.g. `CUSTOM_EMOJI_INVALID` or a rights error) means the Premium path does NOT hold — STOP and revisit the spec.

- [ ] **Step 3: Echo it to a GROUP/CHANNEL notification target**

Send the same `<tg-emoji>` HTML via `context.bot.send_message(chat_id=<a real whitelist group/channel id>, text=..., parse_mode="HTML")`. Sending rights differ by chat type; the notification surface (Task 7) targets groups/channels, so private-chat success is NOT sufficient. Both must render.

- [ ] **Step 4: Observe group-4 handler coexistence**

While the bot is running, confirm that a normal text/emoji message processed by both the (temporary) handler and the existing group-0 `handle_products_button` causes no errors or duplicate replies. This de-risks Task 5's group-4 `MessageHandler`.

- [ ] **Step 5: Decision gate**

- All of Steps 1–3 render → proceed to Task 1.
- Step 2 or 3 fails → STOP. Report the exact error to the user; the spec's "Premium owner" assumption is wrong and the approach (likely Fragment username, or scope-limited to specific chats) must change before any build.

Remove the spike code afterward (do not commit it).

---

### Task 1: EmojiPlaceholder model + migration

**Files:**
- Create: `src/database/models/emoji_placeholder.py`
- Modify: `src/database/models/notification_settings.py`
- Create: `src/database/migrations/versions/i9d0e1f2a3b4_add_emoji_placeholders.py`
- Test: `tests/test_emoji_placeholder_service.py` (model import smoke only here)

**Interfaces:**
- Produces: `EmojiPlaceholder` ORM model with columns `id:int (PK, autoincrement)`, `name:str`, `content:str|None` (JSON text), `raw_text:str|None`, `set_by:int|None`, `created_at`, `updated_at`. `NotificationSettings.header_placeholder_id:int|None`, `NotificationSettings.footer_placeholder_id:int|None`.

- [ ] **Step 1: Write the model**

Create `src/database/models/emoji_placeholder.py`:

```python
"""
EmojiPlaceholder model — reusable named snippets of Telegram custom (premium)
emoji captured from an admin message, referenced in text via {emo:<id>} tokens.
"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from src.database.models.base import Base


class EmojiPlaceholder(Base):
    """A named placeholder whose content is an ordered list of emoji/text units."""

    __tablename__ = "emoji_placeholders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    # JSON-encoded ordered list of units, e.g.
    # [{"t": "emoji", "id": "5368...", "fb": "🔔"}, {"t": "text", "v": "THÔNG BÁO"}]
    # Null until configured via /set_emo.
    content = Column(Text, nullable=True)
    # Original message text the admin sent, for dashboard preview.
    raw_text = Column(Text, nullable=True)
    # Telegram user id of the admin who configured it.
    set_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2: Add columns to NotificationSettings**

In `src/database/models/notification_settings.py`, add after `topup_notify_chat_ids` and before `created_at`:

```python
    # FK-by-convention (no DB constraint) to emoji_placeholders.id for the
    # notification header/footer. Null = none. Dangling id renders to empty.
    header_placeholder_id = Column(Integer, nullable=True)
    footer_placeholder_id = Column(Integer, nullable=True)
```

Update the import line at the top of that file to include `Integer`:

```python
from sqlalchemy import Column, String, Boolean, Text, DateTime, Integer
```

- [ ] **Step 3: Register the model for metadata**

Confirm models are imported somewhere that runs at startup (e.g. `src/database/models/__init__.py`). Add to that `__init__.py` (mirror existing entries):

```python
from src.database.models.emoji_placeholder import EmojiPlaceholder  # noqa: F401
```

If `src/database/models/__init__.py` does not import models, instead ensure the migration is self-contained (Step 4 does not rely on autogenerate).

- [ ] **Step 4: Write the migration**

Create `src/database/migrations/versions/i9d0e1f2a3b4_add_emoji_placeholders.py`:

```python
"""add emoji_placeholders table + notification header/footer placeholder ids

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-06-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "i9d0e1f2a3b4"
down_revision = "h8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "emoji_placeholders" not in tables:
        op.create_table(
            "emoji_placeholders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=True),
            sa.Column("set_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    ns_cols = [c["name"] for c in inspector.get_columns("notification_settings")]
    if "header_placeholder_id" not in ns_cols:
        op.add_column("notification_settings", sa.Column("header_placeholder_id", sa.Integer(), nullable=True))
    if "footer_placeholder_id" not in ns_cols:
        op.add_column("notification_settings", sa.Column("footer_placeholder_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    ns_cols = [c["name"] for c in inspector.get_columns("notification_settings")]
    if "footer_placeholder_id" in ns_cols:
        op.drop_column("notification_settings", "footer_placeholder_id")
    if "header_placeholder_id" in ns_cols:
        op.drop_column("notification_settings", "header_placeholder_id")

    if "emoji_placeholders" in inspector.get_table_names():
        op.drop_table("emoji_placeholders")
```

- [ ] **Step 5: Write a model smoke test**

Create `tests/test_emoji_placeholder_service.py` with just the imports + table creation for now:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.emoji_placeholder import EmojiPlaceholder


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_model_table_creates_and_inserts():
    session = _session()
    row = EmojiPlaceholder(name="Header")
    session.add(row)
    session.commit()
    assert row.id is not None
    assert row.content is None
```

- [ ] **Step 6: Run the test**

Run: `pytest tests/test_emoji_placeholder_service.py::test_model_table_creates_and_inserts -v`
Expected: PASS

- [ ] **Step 7: Verify migration applies**

Run: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: no errors; `alembic current` shows `i9d0e1f2a3b4`.

- [ ] **Step 8: Commit**

```bash
git add src/database/models/emoji_placeholder.py src/database/models/notification_settings.py src/database/models/__init__.py src/database/migrations/versions/i9d0e1f2a3b4_add_emoji_placeholders.py tests/test_emoji_placeholder_service.py
git commit -m "feat(emoji): add emoji_placeholders model + migration"
```

---

### Task 2: EmojiPlaceholderService (CRUD + render-to-HTML)

**Files:**
- Create: `src/database/services/emoji_placeholder_service.py`
- Test: `tests/test_emoji_placeholder_service.py` (extend)

**Interfaces:**
- Consumes: `EmojiPlaceholder` model.
- Produces:
  - `EmojiPlaceholderService(session)` with `create(name) -> int`, `list_all() -> list[EmojiPlaceholder]`, `get(id) -> EmojiPlaceholder | None`, `rename(id, name) -> EmojiPlaceholder`, `delete(id) -> bool`, `set_content(id, units: list[dict], raw_text: str, set_by: int | None) -> EmojiPlaceholder`, `get_rendered_html(id: int) -> str`.
  - Static `EmojiPlaceholderService.units_to_html(units: list[dict]) -> str`.

> **No cache.** `get_rendered_html` does a single indexed PK lookup + render on each call. An earlier draft cached per id, but the bot and dashboard run as separate processes, so a dashboard-side delete/edit could never invalidate the bot's cache — the lookup is cheap enough that the cache only adds a correctness hazard. Keep it cacheless.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_emoji_placeholder_service.py`:

```python
import json

from src.database.services.emoji_placeholder_service import EmojiPlaceholderService


def test_create_and_get():
    session = _session()
    svc = EmojiPlaceholderService(session)
    pid = svc.create("Header")
    assert isinstance(pid, int)
    row = svc.get(pid)
    assert row.name == "Header"
    assert row.content is None


def test_set_content_stores_json_and_renders():
    session = _session()
    svc = EmojiPlaceholderService(session)
    pid = svc.create("Banner")
    units = [
        {"t": "emoji", "id": "5368324170671202286", "fb": "🔔"},
        {"t": "text", "v": "THÔNG BÁO"},
    ]
    svc.set_content(pid, units, raw_text="🔔THÔNG BÁO", set_by=42)
    row = svc.get(pid)
    assert json.loads(row.content) == units
    assert row.set_by == 42
    html = svc.get_rendered_html(pid)
    assert html == '<tg-emoji emoji-id="5368324170671202286">🔔</tg-emoji>THÔNG BÁO'


def test_units_to_html_escapes_text_units():
    html = EmojiPlaceholderService.units_to_html([{"t": "text", "v": "a < b & c"}])
    assert html == "a &lt; b &amp; c"


def test_get_rendered_html_missing_or_empty_returns_blank():
    session = _session()
    svc = EmojiPlaceholderService(session)
    assert svc.get_rendered_html(999) == ""
    pid = svc.create("Empty")
    assert svc.get_rendered_html(pid) == ""


def test_render_reflects_updated_content():
    session = _session()
    svc = EmojiPlaceholderService(session)
    pid = svc.create("X")
    svc.set_content(pid, [{"t": "text", "v": "one"}], raw_text="one", set_by=None)
    assert svc.get_rendered_html(pid) == "one"
    svc.set_content(pid, [{"t": "text", "v": "two"}], raw_text="two", set_by=None)
    assert svc.get_rendered_html(pid) == "two"


def test_delete_removes():
    session = _session()
    svc = EmojiPlaceholderService(session)
    pid = svc.create("Y")
    svc.set_content(pid, [{"t": "text", "v": "hi"}], raw_text="hi", set_by=None)
    assert svc.get_rendered_html(pid) == "hi"
    assert svc.delete(pid) is True
    assert svc.get_rendered_html(pid) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_emoji_placeholder_service.py -v`
Expected: FAIL with `ModuleNotFoundError: ... emoji_placeholder_service`

- [ ] **Step 3: Write the service**

Create `src/database/services/emoji_placeholder_service.py`:

```python
"""
EmojiPlaceholderService — CRUD for emoji placeholders plus rendering captured
unit lists to Telegram <tg-emoji> HTML.
"""
import html
import json
from typing import List, Optional

from sqlalchemy.orm import Session

from src.database.models.emoji_placeholder import EmojiPlaceholder


class EmojiPlaceholderService:
    """CRUD + rendering for emoji placeholders."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- queries -----------------------------------------------------------
    def list_all(self) -> List[EmojiPlaceholder]:
        return (
            self.session.query(EmojiPlaceholder)
            .order_by(EmojiPlaceholder.id.asc())
            .all()
        )

    def get(self, placeholder_id: int) -> Optional[EmojiPlaceholder]:
        return self.session.get(EmojiPlaceholder, placeholder_id)

    # ---- mutations ---------------------------------------------------------
    def create(self, name: str) -> int:
        row = EmojiPlaceholder(name=name)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row.id

    def rename(self, placeholder_id: int, name: str) -> EmojiPlaceholder:
        row = self.get(placeholder_id)
        if row is None:
            raise ValueError(f"placeholder {placeholder_id} not found")
        row.name = name
        self.session.commit()
        self.session.refresh(row)
        return row

    def set_content(
        self,
        placeholder_id: int,
        units: List[dict],
        raw_text: str,
        set_by: Optional[int],
    ) -> EmojiPlaceholder:
        row = self.get(placeholder_id)
        if row is None:
            raise ValueError(f"placeholder {placeholder_id} not found")
        row.content = json.dumps(units, ensure_ascii=False)
        row.raw_text = raw_text
        row.set_by = set_by
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete(self, placeholder_id: int) -> bool:
        row = self.get(placeholder_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    # ---- rendering ---------------------------------------------------------
    @staticmethod
    def units_to_html(units: List[dict]) -> str:
        parts: List[str] = []
        for unit in units:
            if unit.get("t") == "emoji":
                fallback = html.escape(unit.get("fb", ""))
                parts.append(
                    f'<tg-emoji emoji-id="{unit["id"]}">{fallback}</tg-emoji>'
                )
            else:
                parts.append(html.escape(unit.get("v", "")))
        return "".join(parts)

    def get_rendered_html(self, placeholder_id: int) -> str:
        """Return rendered HTML for a placeholder, or '' if missing/empty."""
        row = self.get(placeholder_id)
        if row is None or not row.content:
            return ""
        return self.units_to_html(json.loads(row.content))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_emoji_placeholder_service.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/database/services/emoji_placeholder_service.py tests/test_emoji_placeholder_service.py
git commit -m "feat(emoji): EmojiPlaceholderService CRUD + render + cache"
```

---

### Task 3: Capture parser — `parse_emoji_units`

**Files:**
- Create: `src/bot/messages/emoji_renderer.py` (parser part)
- Test: `tests/test_emoji_renderer.py`

**Interfaces:**
- Produces: `parse_emoji_units(text: str, entities: Iterable) -> list[dict]`. Each entity is any object with `.type` (str), `.offset` (int, UTF-16 units), `.length` (int, UTF-16 units), and `.custom_emoji_id` (str). Returns ordered units `{"t":"emoji","id":...,"fb":...}` / `{"t":"text","v":...}`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_emoji_renderer.py`:

```python
from dataclasses import dataclass
from typing import Optional

from src.bot.messages.emoji_renderer import parse_emoji_units


@dataclass
class FakeEntity:
    type: str
    offset: int
    length: int
    custom_emoji_id: Optional[str] = None


def test_parse_emoji_only():
    # "🔔" is 1 code point but 2 UTF-16 code units (surrogate pair).
    text = "🔔"
    entities = [FakeEntity("custom_emoji", 0, 2, "111")]
    assert parse_emoji_units(text, entities) == [
        {"t": "emoji", "id": "111", "fb": "🔔"}
    ]


def test_parse_mixed_text_and_emoji():
    text = "🔔THÔNG BÁO"
    entities = [FakeEntity("custom_emoji", 0, 2, "111")]
    assert parse_emoji_units(text, entities) == [
        {"t": "emoji", "id": "111", "fb": "🔔"},
        {"t": "text", "v": "THÔNG BÁO"},
    ]


def test_parse_two_emoji_with_gap():
    text = "🔔X🔥"
    entities = [
        FakeEntity("custom_emoji", 0, 2, "111"),
        FakeEntity("custom_emoji", 3, 2, "222"),
    ]
    assert parse_emoji_units(text, entities) == [
        {"t": "emoji", "id": "111", "fb": "🔔"},
        {"t": "text", "v": "X"},
        {"t": "emoji", "id": "222", "fb": "🔥"},
    ]


def test_parse_ignores_non_custom_entities():
    text = "hello"
    entities = [FakeEntity("bold", 0, 5)]
    assert parse_emoji_units(text, entities) == [{"t": "text", "v": "hello"}]


def test_parse_plain_text_no_entities():
    assert parse_emoji_units("just text", []) == [{"t": "text", "v": "just text"}]


def test_parse_empty():
    assert parse_emoji_units("", []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_emoji_renderer.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_emoji_units'`

- [ ] **Step 3: Write the parser**

Create `src/bot/messages/emoji_renderer.py`:

```python
"""
Emoji rendering for the bot:
- parse_emoji_units: turn an incoming message (text + entities) into an ordered
  list of emoji/text units (capture side of /set_emo).
- render: replace {emo:<id>} tokens in outgoing text with <tg-emoji> HTML,
  HTML-escaping all surrounding human content first (render side).
"""
import html
import re
from typing import Iterable, List, Optional, Tuple

CUSTOM_EMOJI_TYPE = "custom_emoji"
_TOKEN_RE = re.compile(r"\{emo:(\d+)\}")


def parse_emoji_units(text: str, entities: Iterable) -> List[dict]:
    """
    Build an ordered unit list from message text + entities.

    Telegram entity offset/length are counted in UTF-16 code units, so we work
    in a UTF-16-LE byte buffer (2 bytes per code unit).
    """
    text = text or ""
    if not text:
        return []

    custom = [
        e
        for e in (entities or [])
        if getattr(e, "type", None) == CUSTOM_EMOJI_TYPE
    ]
    custom.sort(key=lambda e: e.offset)

    buf = text.encode("utf-16-le")
    total_units = len(buf) // 2

    def slice_u16(start: int, length: int) -> str:
        return buf[start * 2 : (start + length) * 2].decode("utf-16-le")

    units: List[dict] = []
    cursor = 0
    for e in custom:
        if e.offset > cursor:
            units.append({"t": "text", "v": slice_u16(cursor, e.offset - cursor)})
        units.append(
            {
                "t": "emoji",
                "id": str(e.custom_emoji_id),
                "fb": slice_u16(e.offset, e.length),
            }
        )
        cursor = e.offset + e.length

    if cursor < total_units:
        units.append({"t": "text", "v": slice_u16(cursor, total_units - cursor)})

    return units
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_emoji_renderer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/messages/emoji_renderer.py tests/test_emoji_renderer.py
git commit -m "feat(emoji): parse_emoji_units capture parser"
```

---

### Task 4: Token renderer — `render`

**Files:**
- Modify: `src/bot/messages/emoji_renderer.py` (add `render`)
- Test: `tests/test_emoji_renderer.py` (extend)

**Interfaces:**
- Consumes: `EmojiPlaceholderService.get_rendered_html(id)`.
- Produces: `render(text: str, service) -> tuple[str, Optional[str]]`. Returns `(text, None)` when no `{emo:` token present; otherwise `(html_string, "HTML")`. `service` is any object exposing `get_rendered_html(id: int) -> str`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_emoji_renderer.py`:

```python
from src.bot.messages.emoji_renderer import render


class FakeService:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_rendered_html(self, pid):
        return self.mapping.get(pid, "")


def test_render_no_token_passthrough():
    svc = FakeService({})
    assert render("plain text", svc) == ("plain text", None)


def test_render_substitutes_token_and_escapes_surrounding():
    svc = FakeService({5: '<tg-emoji emoji-id="9">🔔</tg-emoji>'})
    text = "a < b {emo:5} end"
    out, mode = render(text, svc)
    assert mode == "HTML"
    assert out == 'a &lt; b <tg-emoji emoji-id="9">🔔</tg-emoji> end'


def test_render_missing_placeholder_drops_token():
    svc = FakeService({})
    out, mode = render("hi {emo:7} there", svc)
    assert mode == "HTML"
    assert out == "hi  there"


def test_render_multiple_tokens():
    svc = FakeService({1: "A", 2: "B"})
    out, mode = render("{emo:1}-{emo:2}", svc)
    assert out == "A-B"
    assert mode == "HTML"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_emoji_renderer.py -k render -v`
Expected: FAIL with `ImportError: cannot import name 'render'`

- [ ] **Step 3: Add `render` to the module**

Append to `src/bot/messages/emoji_renderer.py`:

```python
def render(text: str, service) -> Tuple[str, Optional[str]]:
    """
    Expand {emo:<id>} tokens to <tg-emoji> HTML.

    Returns (text, None) if there is no token (sent as plain text, unchanged).
    Otherwise HTML-escapes the whole string first (so human content is safe),
    then replaces tokens with already-safe placeholder HTML, returning
    (html_string, "HTML").
    """
    if "{emo:" not in text:
        return text, None

    escaped = html.escape(text)  # tokens contain no HTML-special chars, survive

    def _replace(match: "re.Match[str]") -> str:
        return service.get_rendered_html(int(match.group(1)))

    return _TOKEN_RE.sub(_replace, escaped), "HTML"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_emoji_renderer.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/bot/messages/emoji_renderer.py tests/test_emoji_renderer.py
git commit -m "feat(emoji): render() token-to-HTML with escaping"
```

---

### Task 5: `/set_emo` command + capture handler

**Files:**
- Modify: `src/bot/states/state_manager.py`
- Create: `src/bot/handlers/emoji_admin.py`
- Modify: `src/bot/main.py`
- Test: `tests/test_emoji_capture_handler.py`

**Interfaces:**
- Consumes: `is_admin` (`src/bot/utils/admin_check.py`), `get_session_factory`, `EmojiPlaceholderService`, `parse_emoji_units`, `state_manager` (the module singleton used by other handlers — import the same instance).
- Produces: `set_emo_command(update, context)`, `handle_emoji_capture(update, context)`; new `UserState` fields `awaiting_emoji_input: bool`, `pending_emoji_placeholder_id: Optional[int]`.

- [ ] **Step 1: Add state fields**

In `src/bot/states/state_manager.py`, add to the `UserState` dataclass (after the `/export` block):

```python
    # /set_emo flow state
    awaiting_emoji_input: bool = False
    pending_emoji_placeholder_id: Optional[int] = None
```

(No change to `update_user_state` — the handler mutates these fields directly via `get_user_state`/`set_user_state`.)

- [ ] **Step 2: Write the failing test for unit extraction wiring**

Create `tests/test_emoji_capture_handler.py`:

```python
from dataclasses import dataclass, field
from typing import List, Optional

from src.bot.handlers.emoji_admin import extract_units_from_message


@dataclass
class FakeEntity:
    type: str
    offset: int
    length: int
    custom_emoji_id: Optional[str] = None


@dataclass
class FakeMessage:
    text: str
    entities: List[FakeEntity] = field(default_factory=list)


def test_extract_units_from_message():
    msg = FakeMessage(text="🔔OK", entities=[FakeEntity("custom_emoji", 0, 2, "111")])
    assert extract_units_from_message(msg) == [
        {"t": "emoji", "id": "111", "fb": "🔔"},
        {"t": "text", "v": "OK"},
    ]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_emoji_capture_handler.py -v`
Expected: FAIL with `ModuleNotFoundError: ... emoji_admin`

- [ ] **Step 4: Write the handler module**

Create `src/bot/handlers/emoji_admin.py`:

```python
"""
Admin /set_emo flow: capture premium-emoji content for a placeholder.

Step 1: /set_emo <id>           -> mark state awaiting input for that placeholder
Step 2: next message (emoji)    -> read custom_emoji entities, store units
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.handlers.commands import state_manager
from src.bot.messages.emoji_renderer import parse_emoji_units
from src.bot.utils.admin_check import is_admin
from src.database.connection import get_session_factory
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService

logger = logging.getLogger(__name__)


def extract_units_from_message(message) -> list:
    """Pure helper: build unit list from a message-like object."""
    return parse_emoji_units(getattr(message, "text", "") or "", getattr(message, "entities", []) or [])


async def set_emo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/set_emo <id> — begin capturing emoji for a placeholder (admins only)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ No permission.")
        return

    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /set_emo <placeholder_id>")
        return

    placeholder_id = int(args[0])
    session = get_session_factory()()
    try:
        svc = EmojiPlaceholderService(session)
        row = svc.get(placeholder_id)
        if row is None:
            await update.message.reply_text(f"Placeholder {placeholder_id} not found.")
            return
        name = row.name
    finally:
        session.close()

    state = state_manager.get_user_state(user.id)
    if state is None:
        from src.bot.states.state_manager import UserState
        state = UserState()
    state.awaiting_emoji_input = True
    state.pending_emoji_placeholder_id = placeholder_id
    state_manager.set_user_state(user.id, state)

    await update.message.reply_text(
        f"Send the premium emoji(s) for placeholder {placeholder_id} ('{name}')."
    )


async def handle_emoji_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Second step: capture the emoji message that follows /set_emo."""
    user = update.effective_user
    message = update.message
    if not user or not message:
        return

    state = state_manager.get_user_state(user.id)
    if not state or not state.awaiting_emoji_input:
        return  # not in capture mode; let other handlers deal with it

    if not is_admin(user.id):
        return

    placeholder_id = state.pending_emoji_placeholder_id
    units = extract_units_from_message(message)

    state.awaiting_emoji_input = False
    state.pending_emoji_placeholder_id = None
    state_manager.set_user_state(user.id, state)

    emoji_count = sum(1 for u in units if u.get("t") == "emoji")
    if emoji_count == 0:
        await message.reply_text(
            "No custom emoji found in that message. Run /set_emo again and send "
            "premium (animated) emoji."
        )
        return

    session = get_session_factory()()
    try:
        svc = EmojiPlaceholderService(session)
        svc.set_content(
            placeholder_id, units, raw_text=message.text or "", set_by=user.id
        )
    except ValueError:
        await message.reply_text(f"Placeholder {placeholder_id} no longer exists.")
        return
    finally:
        session.close()

    await message.reply_text(
        f"✅ Captured {emoji_count} custom emoji for placeholder {placeholder_id}. "
        f"Use it anywhere with {{emo:{placeholder_id}}}."
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_emoji_capture_handler.py -v`
Expected: PASS

- [ ] **Step 6: Register handlers in main.py**

In `src/bot/main.py`, add the import near the other handler imports:

```python
from src.bot.handlers.emoji_admin import set_emo_command, handle_emoji_capture
```

Add the command handler alongside the others (after `CommandHandler("setadmin", setadmin_command)`):

```python
    application.add_handler(CommandHandler("set_emo", set_emo_command))
```

Add the capture message handler in its own group (after the existing group-3 handler registration). Ensure `filters` and `MessageHandler` are imported (they already are in main.py):

```python
    # Emoji capture: only acts when the user is in /set_emo awaiting state.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emoji_capture),
        group=4,
    )
```

- [ ] **Step 7: Verify the suite still imports/loads**

Run: `pytest tests/test_emoji_capture_handler.py tests/test_emoji_renderer.py -v`
Expected: PASS. Then `python -c "import src.bot.main"` → no import errors.

- [ ] **Step 8: Commit**

```bash
git add src/bot/states/state_manager.py src/bot/handlers/emoji_admin.py src/bot/main.py tests/test_emoji_capture_handler.py
git commit -m "feat(emoji): /set_emo capture command + handler"
```

---

### Task 6: Render product list & detail messages

**Files:**
- Modify: `src/bot/handlers/callbacks.py`
- Test: manual + suite (no pure unit test for the Telegram send call)

**Interfaces:**
- Consumes: `emoji_renderer.render`, `EmojiPlaceholderService`, the existing session in `callbacks.py`.

- [ ] **Step 1: Add a small render helper at the product-detail send site**

In `src/bot/handlers/callbacks.py`, locate the product-detail block (around the `formatter.format_product_detail(...)` call that ends with `await query.edit_message_text(message, reply_markup=keyboard)`).

Add imports at the top of the file (with the other imports):

```python
from src.bot.messages.emoji_renderer import render as render_emoji
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
```

- [ ] **Step 2: Render before sending product detail**

Replace the send call:

```python
await query.edit_message_text(message, reply_markup=keyboard)
```

with (reuse the session already open in this handler; if none is open in scope, open one with `get_session_factory()()` and close it in `finally`):

```python
rendered, parse_mode = render_emoji(message, EmojiPlaceholderService(session))
await query.edit_message_text(rendered, reply_markup=keyboard, parse_mode=parse_mode)
```

> If the product-detail block does not already have a `session` variable in scope, wrap with:
> ```python
> session = get_session_factory()()
> try:
>     rendered, parse_mode = render_emoji(message, EmojiPlaceholderService(session))
> finally:
>     session.close()
> await query.edit_message_text(rendered, reply_markup=keyboard, parse_mode=parse_mode)
> ```
> (`get_session_factory` is already imported in `callbacks.py`; confirm and add the import if not.)

- [ ] **Step 3: Render the product list send site**

Find where `formatter.format_product_list(...)` output is sent (the products list view, also in `callbacks.py` / `handlers/commands.py products_command`). Apply the same pattern at that send call:

```python
rendered, parse_mode = render_emoji(message, EmojiPlaceholderService(session))
await query.edit_message_text(rendered, reply_markup=keyboard, parse_mode=parse_mode)
```

If the list text is the zero-width-space fallback (`"​"`), `render` returns `(text, None)` unchanged — safe.

- [ ] **Step 4: Verify the suite still passes**

Run: `pytest tests/test_emoji_renderer.py -v && pytest -q`
Expected: emoji tests PASS; no NEW failures vs. the pre-existing baseline (per repo notes, ~52 env-driven failures pre-exist; compare counts, don't introduce new ones).

- [ ] **Step 5: Manual verification**

Run the bot locally, create+configure a placeholder (Tasks 1–5 path), put `{emo:<id>}` in a product description via dashboard, open that product in the bot. Confirm the premium emoji renders and no `&lt;`/raw-tag artifacts appear.

- [ ] **Step 6: Commit**

```bash
git add src/bot/handlers/callbacks.py
git commit -m "feat(emoji): render emoji tokens in product list/detail"
```

---

### Task 7: Notification header/footer + body rendering

**Files:**
- Modify: `src/database/services/order_notification_service.py`
- Test: `tests/test_notification_emoji.py`

**Interfaces:**
- Consumes: `EmojiPlaceholderService`, `emoji_renderer.render`, `NotificationSettings.header_placeholder_id/footer_placeholder_id`.
- Produces: `OrderNotificationService._compose_with_emoji(message: str) -> tuple[str, Optional[str]]`.

- [ ] **Step 1: Write failing test**

Create `tests/test_notification_emoji.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.notification_settings_service import NotificationSettingsService
from src.database.services.order_notification_service import OrderNotificationService


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_compose_plain_when_no_header_footer():
    session = _session()
    svc = OrderNotificationService(session, bot=None)
    text, mode = svc._compose_with_emoji("hello")
    assert (text, mode) == ("hello", None)


def test_compose_wraps_header_and_footer():
    session = _session()
    emoji_svc = EmojiPlaceholderService(session)
    hid = emoji_svc.create("H")
    emoji_svc.set_content(hid, [{"t": "text", "v": "TOP"}], raw_text="TOP", set_by=None)
    fid = emoji_svc.create("F")
    emoji_svc.set_content(fid, [{"t": "text", "v": "BOT"}], raw_text="BOT", set_by=None)

    settings_svc = NotificationSettingsService(session)
    settings = settings_svc.get_settings()
    settings.header_placeholder_id = hid
    settings.footer_placeholder_id = fid
    session.commit()

    svc = OrderNotificationService(session, bot=None)
    text, mode = svc._compose_with_emoji("body")
    assert mode == "HTML"
    assert text == "TOP\nbody\nBOT"
```

> NOTE: Confirm `OrderNotificationService.__init__` accepts `(session, bot=None)`. If its signature differs, adjust the test's construction to match (check the real `__init__`).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_notification_emoji.py -v`
Expected: FAIL with `AttributeError: ... _compose_with_emoji`

- [ ] **Step 3: Add the compose method and use it in the send path**

In `src/database/services/order_notification_service.py`, add imports:

```python
from src.bot.messages.emoji_renderer import render as render_emoji
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
```

Add the method (anywhere in the class):

```python
    def _compose_with_emoji(self, message: str):
        """
        Prepend/append the configured header/footer placeholders (as {emo:id}
        tokens) and render the whole thing. Returns (text, parse_mode).
        """
        settings = self._settings_service.get_settings()
        combined = message
        header_id = getattr(settings, "header_placeholder_id", None)
        footer_id = getattr(settings, "footer_placeholder_id", None)
        if header_id:
            combined = f"{{emo:{header_id}}}\n{combined}"
        if footer_id:
            combined = f"{combined}\n{{emo:{footer_id}}}"
        return render_emoji(combined, EmojiPlaceholderService(self.session))
```

In `send_message_to_whitelist_async`, replace the per-target text assignment. Compute once before the loop:

```python
        rendered_message, parse_mode = self._compose_with_emoji(message)
```

and change `send_kwargs` inside the loop:

```python
        send_kwargs = {
            "chat_id": chat_id,
            "text": rendered_message,
        }
        if parse_mode is not None:
            send_kwargs["parse_mode"] = parse_mode
        if message_thread_id is not None:
            send_kwargs["message_thread_id"] = int(message_thread_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_notification_emoji.py -v`
Expected: PASS

- [ ] **Step 5: Regression check**

Run: `pytest -q`
Expected: no NEW failures vs. baseline.

- [ ] **Step 6: Commit**

```bash
git add src/database/services/order_notification_service.py tests/test_notification_emoji.py
git commit -m "feat(emoji): notification header/footer + token rendering"
```

---

### Task 8: Dashboard CRUD API for placeholders

**Files:**
- Create: `src/dashboard/routers/emoji_placeholders.py`
- Modify: `src/dashboard/main.py`
- Test: `tests/test_emoji_placeholders_api.py`

**Interfaces:**
- Consumes: `EmojiPlaceholderService`, `get_db`, `require_admin_role`, `require_viewer_or_admin`.
- Produces: REST endpoints under `/api/emoji-placeholders` returning `EmojiPlaceholderResponse {id, name, configured: bool, raw_text: str|None, token: str}`.

- [ ] **Step 1: Write failing API test**

Create `tests/test_emoji_placeholders_api.py`:

```python
from fastapi.testclient import TestClient

from src.dashboard.routers import emoji_placeholders


def test_response_token_format():
    resp = emoji_placeholders.EmojiPlaceholderResponse(
        id=5, name="Header", configured=False, raw_text=None
    )
    assert resp.token == "{emo:5}"
    assert resp.configured is False
```

> This is a unit test of the schema (no auth/DB harness needed). Full HTTP-level testing is covered by manual verification in Step 5, mirroring how other routers are exercised in this repo.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_emoji_placeholders_api.py -v`
Expected: FAIL with `ModuleNotFoundError: ... emoji_placeholders`

- [ ] **Step 3: Write the router**

Create `src/dashboard/routers/emoji_placeholders.py`:

```python
"""Dashboard CRUD API for emoji placeholders."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, computed_field
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService

router = APIRouter()


class EmojiPlaceholderResponse(BaseModel):
    id: int
    name: str
    configured: bool
    raw_text: Optional[str] = None

    @computed_field
    @property
    def token(self) -> str:
        return f"{{emo:{self.id}}}"


class EmojiPlaceholderCreate(BaseModel):
    name: str


class EmojiPlaceholderUpdate(BaseModel):
    name: str


def _to_response(row) -> EmojiPlaceholderResponse:
    return EmojiPlaceholderResponse(
        id=row.id,
        name=row.name,
        configured=bool(row.content),
        raw_text=row.raw_text,
    )


@router.get("", response_model=List[EmojiPlaceholderResponse], include_in_schema=True)
@router.get("/", response_model=List[EmojiPlaceholderResponse], include_in_schema=False)
async def list_placeholders(
    current_admin=Depends(require_viewer_or_admin),
    db: Session = Depends(get_db),
):
    return [_to_response(r) for r in EmojiPlaceholderService(db).list_all()]


@router.post("", response_model=EmojiPlaceholderResponse, status_code=status.HTTP_201_CREATED, include_in_schema=True)
@router.post("/", response_model=EmojiPlaceholderResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_placeholder(
    payload: EmojiPlaceholderCreate,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    svc = EmojiPlaceholderService(db)
    pid = svc.create(payload.name)
    return _to_response(svc.get(pid))


@router.put("/{placeholder_id}", response_model=EmojiPlaceholderResponse)
async def rename_placeholder(
    placeholder_id: int,
    payload: EmojiPlaceholderUpdate,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    svc = EmojiPlaceholderService(db)
    try:
        row = svc.rename(placeholder_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(row)


@router.delete("/{placeholder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_placeholder(
    placeholder_id: int,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    if not EmojiPlaceholderService(db).delete(placeholder_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return None
```

> If this repo's Pydantic version lacks `computed_field` (Pydantic v1), instead set `token` in `_to_response` by adding `token: str` as a normal field and passing `token=f"{{emo:{row.id}}}"`. Verify the Pydantic major version in `requirements.txt` before choosing.

- [ ] **Step 4: Mount the router**

In `src/dashboard/main.py`, add `emoji_placeholders` to the `from src.dashboard.routers import (...)` block, then add near the other mounts:

```python
app.include_router(emoji_placeholders.router, prefix="/api/emoji-placeholders", tags=["emoji-placeholders"])
```

- [ ] **Step 5: Run test + manual check**

Run: `pytest tests/test_emoji_placeholders_api.py -v`
Expected: PASS.
Manual: start the dashboard, `POST /api/emoji-placeholders {"name":"Header"}` returns `{id, token:"{emo:1}", configured:false}`; `GET` lists it; `DELETE` removes it.

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/routers/emoji_placeholders.py src/dashboard/main.py tests/test_emoji_placeholders_api.py
git commit -m "feat(emoji): dashboard CRUD API for placeholders"
```

---

### Task 9: Notifications router — header/footer fields

**Files:**
- Modify: `src/dashboard/routers/notifications.py`
- Modify: `src/database/services/notification_settings_service.py`
- Test: `tests/test_notification_settings_placeholder_fields.py`

**Interfaces:**
- Produces: `NotificationSettingsService.update_settings(..., header_placeholder_id=None, footer_placeholder_id=None)` persists the two ints; `OrderNotificationSettingsResponse`/`...Update` carry `header_placeholder_id: int|None`, `footer_placeholder_id: int|None`.

- [ ] **Step 1: Write failing test**

Create `tests/test_notification_settings_placeholder_fields.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.services.notification_settings_service import NotificationSettingsService


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_update_persists_placeholder_ids():
    session = _session()
    svc = NotificationSettingsService(session)
    settings = svc.update_settings(
        order_notify_enabled=True,
        order_notify_on_created=False,
        order_notify_on_paid=True,
        topup_notify_on_paid=False,
        whitelist_chat_ids=[],
        upgrade_chat_ids=[],
        topup_chat_ids=[],
        header_placeholder_id=3,
        footer_placeholder_id=None,
    )
    assert settings.header_placeholder_id == 3
    assert settings.footer_placeholder_id is None
```

> Confirm the real `update_settings` signature/keywords (whitelist param names) and match them exactly in the test.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_notification_settings_placeholder_fields.py -v`
Expected: FAIL (`update_settings() got an unexpected keyword argument 'header_placeholder_id'`).

- [ ] **Step 3: Extend the service**

In `src/database/services/notification_settings_service.py`, add two keyword params to `update_settings` (default `None`) and apply them only when provided, e.g.:

```python
        if header_placeholder_id is not None or _set_header:
            settings.header_placeholder_id = header_placeholder_id
        if footer_placeholder_id is not None or _set_footer:
            settings.footer_placeholder_id = footer_placeholder_id
```

Simplest correct form — accept the values and assign directly (allowing clearing to None) by adding explicit params and always assigning:

```python
    def update_settings(
        self,
        *,
        order_notify_enabled,
        order_notify_on_created,
        order_notify_on_paid,
        topup_notify_on_paid,
        whitelist_chat_ids,
        upgrade_chat_ids,
        topup_chat_ids,
        header_placeholder_id=None,
        footer_placeholder_id=None,
    ):
        settings = self.get_settings()
        # ... existing assignments ...
        settings.header_placeholder_id = header_placeholder_id
        settings.footer_placeholder_id = footer_placeholder_id
        self.session.commit()
        self.session.refresh(settings)
        return settings
```

> Match the EXISTING parameter style of `update_settings` (positional vs keyword). Keep all current assignments; only add the two new ones. If the existing signature is positional, append the two new params with `=None` defaults at the end.

- [ ] **Step 4: Run service test to verify it passes**

Run: `pytest tests/test_notification_settings_placeholder_fields.py -v`
Expected: PASS

- [ ] **Step 5: Add fields to the router schemas + endpoints**

In `src/dashboard/routers/notifications.py`, add to both `OrderNotificationSettingsResponse` and `OrderNotificationSettingsUpdate`:

```python
    header_placeholder_id: Optional[int] = None
    footer_placeholder_id: Optional[int] = None
```

(ensure `from typing import Optional` is imported). In the GET endpoint response construction add:

```python
        header_placeholder_id=settings.header_placeholder_id,
        footer_placeholder_id=settings.footer_placeholder_id,
```

In the PUT endpoint, pass through to the service:

```python
        header_placeholder_id=payload.header_placeholder_id,
        footer_placeholder_id=payload.footer_placeholder_id,
```

and include the two fields in the PUT response construction (same as GET).

- [ ] **Step 6: Regression check**

Run: `pytest -q`
Expected: no NEW failures.

- [ ] **Step 7: Commit**

```bash
git add src/dashboard/routers/notifications.py src/database/services/notification_settings_service.py tests/test_notification_settings_placeholder_fields.py
git commit -m "feat(emoji): notification settings header/footer placeholder ids"
```

---

### Task 10: Frontend — Emoji placeholders page + nav + route

**Files:**
- Create: `frontend/src/pages/EmojiPlaceholdersPage.tsx`
- Modify: `frontend/src/app/routes.ts`, `frontend/src/App.tsx`, `frontend/src/app/layouts/Sidebar.tsx`
- Modify: i18n locale resource (add `nav.emojiPlaceholders` + page strings)
- Test: rely on `npm run build` + `npm test` (routing smoke)

**Interfaces:**
- Consumes: `apiClient`, `formatApiError`, shared components (`PageHeader`, `Button`, `IconButton`, `FormField`, `Select`, `Toast`).

- [ ] **Step 1: Add the route definition**

In `frontend/src/app/routes.ts`, add to `ROUTES` (settings group):

```typescript
  { path: '/emoji-placeholders', key: 'emojiPlaceholders', labelKey: 'nav.emojiPlaceholders', group: 'settings', iconName: 'Smile' },
```

- [ ] **Step 2: Ensure the icon is mapped**

In `frontend/src/app/layouts/Sidebar.tsx`, confirm `ICON_MAP` includes `Smile`; if not, import it from `lucide-react` and add `Smile,` to the map (mirror existing icon entries).

- [ ] **Step 3: Register the route in App.tsx**

In `frontend/src/App.tsx`, import the page and add the nested route:

```typescript
import { EmojiPlaceholdersPage } from './pages/EmojiPlaceholdersPage'
// ...
          <Route path="emoji-placeholders" element={<EmojiPlaceholdersPage />} />
```

- [ ] **Step 4: Add i18n strings**

In the locale resource files (mirror where `nav.generalSettings` is defined), add:

```json
"nav": { "emojiPlaceholders": "Emoji" },
"emoji": {
  "title": "Emoji Placeholders",
  "create": "New placeholder",
  "namePlaceholder": "Name (e.g. Header banner)",
  "configured": "Configured",
  "empty": "Empty",
  "setHint": "Run /set_emo {id} in the bot and send your premium emoji",
  "copyToken": "Copy token",
  "deleteConfirm": "Delete this placeholder?",
  "loadError": "Could not load placeholders",
  "saveError": "Could not save"
}
```

(Add to both `vi` and `en` resources; Vietnamese values may mirror English for now.)

- [ ] **Step 5: Create the page component**

Create `frontend/src/pages/EmojiPlaceholdersPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Plus, Trash2, Copy, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Button } from '../shared/components/Button'
import { IconButton } from '../shared/components/IconButton'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'

interface EmojiPlaceholder {
  id: number
  name: string
  configured: boolean
  raw_text: string | null
  token: string
}

export function EmojiPlaceholdersPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [items, setItems] = useState<EmojiPlaceholder[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const fetchItems = async () => {
    setLoading(true)
    try {
      const res = await apiClient.get<EmojiPlaceholder[]>('/api/emoji-placeholders')
      setItems(res.data)
    } catch (err) {
      toast.error(formatApiError(err, t('emoji.loadError', 'Could not load placeholders')))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchItems() }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      await apiClient.post('/api/emoji-placeholders', { name: newName.trim() })
      setNewName('')
      await fetchItems()
    } catch (err) {
      toast.error(formatApiError(err, t('emoji.saveError', 'Could not save')))
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm(t('emoji.deleteConfirm', 'Delete this placeholder?'))) return
    try {
      await apiClient.delete(`/api/emoji-placeholders/${id}`)
      await fetchItems()
    } catch (err) {
      toast.error(formatApiError(err, t('emoji.saveError', 'Could not save')))
    }
  }

  const copyToken = (token: string) => {
    navigator.clipboard?.writeText(token)
    toast.success(token)
  }

  return (
    <div className="emoji-placeholders-page">
      <PageHeader
        title={t('emoji.title', 'Emoji Placeholders')}
        actions={
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.refresh', 'Refresh')}
            variant="ghost"
            size="sm"
            onClick={fetchItems}
          />
        }
      />

      <div className="emoji-placeholders-page__create" style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder={t('emoji.namePlaceholder', 'Name (e.g. Header banner)')}
          onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
        />
        <Button variant="primary" size="sm" iconLeft={<Plus size={14} />} onClick={handleCreate} loading={creating}>
          {t('emoji.create', 'New placeholder')}
        </Button>
      </div>

      {loading ? (
        <p>…</p>
      ) : (
        <table className="emoji-placeholders-page__table">
          <thead>
            <tr>
              <th>ID</th><th>Name</th><th>Token</th><th>Status</th><th>Preview</th><th></th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.name}</td>
                <td>
                  <code>{item.token}</code>
                  <IconButton icon={<Copy size={12} />} aria-label={t('emoji.copyToken', 'Copy token')} variant="ghost" size="sm" onClick={() => copyToken(item.token)} />
                </td>
                <td>{item.configured ? t('emoji.configured', 'Configured') : t('emoji.empty', 'Empty')}</td>
                <td>{item.configured ? item.raw_text : <span title={t('emoji.setHint', 'Run /set_emo {id} in the bot').replace('{id}', String(item.id))}>—</span>}</td>
                <td>
                  <IconButton icon={<Trash2 size={14} />} aria-label="delete" variant="ghost" size="sm" onClick={() => handleDelete(item.id)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
```

> Match the exact prop names of the shared `Button`/`IconButton`/`PageHeader` components (see `GeneralSettingsPage.tsx`). Styling classes can reuse existing page CSS conventions; inline styles above are placeholders for layout only.

- [ ] **Step 6: Build + routing test**

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds; routing test passes (the new route resolves).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/EmojiPlaceholdersPage.tsx frontend/src/app/routes.ts frontend/src/App.tsx frontend/src/app/layouts/Sidebar.tsx
git commit -m "feat(emoji): dashboard Emoji placeholders page + nav"
```

---

### Task 11: Frontend — Notifications header/footer dropdowns

**Files:**
- Modify: `frontend/src/pages/NotificationsPage.tsx`
- Test: `npm run build` + `npm test`

**Interfaces:**
- Consumes: `/api/emoji-placeholders` (list), `/api/notifications/order-settings` (now carrying `header_placeholder_id`/`footer_placeholder_id`), shared `Select`.

- [ ] **Step 1: Extend the settings type**

In `NotificationsPage.tsx`, add to the `OrderNotificationSettings` interface:

```typescript
  header_placeholder_id: number | null
  footer_placeholder_id: number | null
```

- [ ] **Step 2: Fetch placeholders on mount**

Add state + fetch (alongside `fetchOrderSettings`):

```typescript
  const [placeholders, setPlaceholders] = useState<{ id: number; name: string; token: string }[]>([])

  const fetchPlaceholders = async () => {
    try {
      const res = await apiClient.get<{ id: number; name: string; token: string }[]>('/api/emoji-placeholders')
      setPlaceholders(res.data)
    } catch {
      /* non-fatal: dropdowns just stay empty */
    }
  }
  useEffect(() => { fetchPlaceholders() }, [])
```

- [ ] **Step 3: Add two Select dropdowns to the order-settings form**

Import `Select` and `FormField` if not already. Build options + controls inside the order-settings form block:

```tsx
  const placeholderOptions = [
    { value: '', label: '—' },
    ...placeholders.map(p => ({ value: String(p.id), label: `${p.name} (${p.token})` })),
  ]

  // inside the form JSX:
  <FormField label={t('notifications.headerPlaceholder', 'Notification header')} htmlFor="notif-header">
    <Select
      id="notif-header"
      options={placeholderOptions}
      value={orderSettings?.header_placeholder_id != null ? String(orderSettings.header_placeholder_id) : ''}
      onChange={v => setOrderSettings(s => s ? { ...s, header_placeholder_id: v ? Number(v) : null } : s)}
      searchable
      placeholder={t('notifications.selectPlaceholder', 'Select placeholder…')}
    />
  </FormField>
  <FormField label={t('notifications.footerPlaceholder', 'Notification footer')} htmlFor="notif-footer">
    <Select
      id="notif-footer"
      options={placeholderOptions}
      value={orderSettings?.footer_placeholder_id != null ? String(orderSettings.footer_placeholder_id) : ''}
      onChange={v => setOrderSettings(s => s ? { ...s, footer_placeholder_id: v ? Number(v) : null } : s)}
      searchable
      placeholder={t('notifications.selectPlaceholder', 'Select placeholder…')}
    />
  </FormField>
```

- [ ] **Step 4: Include the fields in save payload**

In `handleSaveOrderSettings`, ensure the spread `...orderSettings` already includes `header_placeholder_id`/`footer_placeholder_id` (it does, since they're on the object). Confirm the PUT body carries them.

- [ ] **Step 5: Add i18n strings**

Add `notifications.headerPlaceholder`, `notifications.footerPlaceholder`, `notifications.selectPlaceholder` to vi + en resources.

- [ ] **Step 6: Build + test**

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds; tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/NotificationsPage.tsx
git commit -m "feat(emoji): notification header/footer placeholder dropdowns"
```

---

### Task 12: Customer order messages — opt-in rendering

**Files:**
- Modify: customer-facing send sites in `src/bot/handlers/` (order confirmation, delivery, balance/topup messages)
- Test: manual + suite

**Interfaces:**
- Consumes: `emoji_renderer.render`, `EmojiPlaceholderService`.

- [ ] **Step 1: Identify the send sites**

Search for customer-facing sends that include admin-authored text (product names, descriptions) or where you want tokens supported:

Run: `rtk proxy grep -rn "edit_message_text\|send_message" src/bot/handlers/ | grep -vi "query.answer"`
Pick the order-confirmation, delivery, and balance/topup message builders.

- [ ] **Step 2: Apply the render helper at each chosen site**

For each, where the text string is built and about to be sent, wrap (reusing an open `session` or opening one):

```python
from src.bot.messages.emoji_renderer import render as render_emoji
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService

rendered, parse_mode = render_emoji(text, EmojiPlaceholderService(session))
await context.bot.send_message(chat_id=chat_id, text=rendered, parse_mode=parse_mode)
# or: await query.edit_message_text(rendered, reply_markup=keyboard, parse_mode=parse_mode)
```

Because `render` returns `(text, None)` when there is no token, sites without tokens keep their current plain-text behavior. Skip any site that already sends `parse_mode="HTML"` with hand-built markup (e.g. the `<pre>` block in `upgrade_handler.py`) — those are out of scope to avoid double-handling.

- [ ] **Step 3: Regression check**

Run: `pytest -q`
Expected: no NEW failures.

- [ ] **Step 4: Manual verification**

Place a test order whose product name/description contains `{emo:<id>}`; confirm the customer-facing confirmation/delivery message renders the premium emoji.

- [ ] **Step 5: Commit**

```bash
git add src/bot/handlers/
git commit -m "feat(emoji): render emoji tokens in customer order messages"
```

---

## Self-Review

**Spec coverage:**
- Data model (table + 2 columns) → Task 1 ✓
- Service CRUD + render + cache → Task 2 ✓
- Capture parsing → Task 3 ✓
- Render helper (escape→substitute, no-token passthrough, missing→empty) → Task 4 ✓
- `/set_emo` two-step capture + admin gating + state fields → Task 5 ✓
- Product list/detail integration → Task 6 ✓
- Notification header/footer + body + escaping → Task 7 ✓
- Dashboard CRUD API → Task 8 ✓
- Notification settings header/footer fields (service + router) → Task 9 ✓
- Dashboard Emoji page + nav + route → Task 10 ✓
- Notifications header/footer dropdowns → Task 11 ✓
- Customer order messages surface → Task 12 ✓
- Testing strategy (capture/renderer/notification assembly, SQLite) → Tasks 2–4, 7, 9 ✓
- Edge cases (escaping, deleted/empty placeholder, non-admin) → Tasks 2,4,5,7 ✓
- Foundation verified empirically before build (Premium-bot send rights, private + group/channel) → Task 0 ✓ (gates all)

**Type consistency:** `render(text, service) -> (str, Optional[str])`, `get_rendered_html(id:int)->str`, `units_to_html(units)->str`, `set_content(id, units, raw_text, set_by)`, `parse_emoji_units(text, entities)->list[dict]`, unit shape `{"t","id"/"v","fb"}` — used consistently across Tasks 2–7. Header/footer stored as `int|None` everywhere (model, service, router, frontend converts via `Number()`).

**Verification-required assumptions (flagged inline in tasks):** exact `OrderNotificationService.__init__` signature (Task 7), exact `update_settings` signature/whitelist keyword names (Task 9), Pydantic major version for `computed_field` (Task 8), presence of a `session` var at the product send sites (Task 6), shared component prop names + `ICON_MAP` (Task 10). Each task instructs the implementer to confirm against the real code before writing.
