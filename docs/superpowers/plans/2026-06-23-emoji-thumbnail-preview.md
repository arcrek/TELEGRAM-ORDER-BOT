# Emoji Thumbnail Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a still image of each configured custom (premium) emoji in the dashboard by lazily fetching Telegram's static emoji thumbnail server-side, caching the bytes in PostgreSQL, and serving them via a public image endpoint.

**Architecture:** A global `emoji_thumbnails` cache table (keyed by `custom_emoji_id`) stores downloaded thumbnail bytes. A public dashboard endpoint serves cached bytes, lazily fetching from Telegram (`getCustomEmojiStickers → getFile → download`) on first request — but only for emoji ids referenced by a stored placeholder. The placeholders list endpoint gains a `units` field so the frontend renders text + `<img>` inline, via a shared `EmojiPreview` component used on the Emoji page and in the notification header/footer dropdowns. No bot-process changes.

**Tech Stack:** python-telegram-bot 22.8 (`Bot.get_custom_emoji_stickers`, `File.download_as_bytearray` confirmed present), SQLAlchemy 2.0, Alembic, FastAPI, React 18 + TypeScript (Vite, axios, vitest), PostgreSQL (SQLite in tests).

## Global Constraints

- **Branch base:** build on `feat/custom-emoji-placeholders` (the parent feature; still local/unmerged). It provides `emoji_placeholders`, `EmojiPlaceholder`, `EmojiPlaceholderService`, the `emoji_placeholders` dashboard router, and content units shaped `{"t":"emoji","id","fb"}` / `{"t":"text","v"}`.
- Bot DB service layer is **synchronous** (`__init__(self, session)`, `self.session`, explicit `commit()`).
- Current Alembic head: `i9d0e1f2a3b4`. New migration chains to it.
- **PostgreSQL-only** in production (`connection.py` raises without DB config). Tests use in-memory SQLite; for tests that need one DB shared across the test session AND a FastAPI dependency override, use `create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)`.
- **Telegram is always mocked in tests** — never a live API call.
- Thumbnails are served as `image/webp`. The image endpoint is **public** (no JWT) but only serves/fetches `custom_emoji_id`s referenced by a stored placeholder.
- Negative-cache TTL = 1 hour (`THUMBNAIL_NEGATIVE_TTL`).
- The dashboard builds a `Bot` from `TELEGRAM_BOT_TOKEN` (mirror `get_bot_instance` in `notifications.py`).
- Frontend: `npm test` is vitest in WATCH mode — use `CI=true npx vitest run`. Image URLs use `apiClient.defaults.baseURL`. Project lints with ruff (Python) and eslint (frontend); keep imports at top.
- Commit after every task.

---

## File Structure

**Backend — create:**
- `src/database/models/emoji_thumbnail.py` — `EmojiThumbnail` model
- `src/database/services/emoji_thumbnail_service.py` — cache CRUD + negative-cache TTL
- `src/dashboard/routers/emoji_thumbnails.py` — fetch helper + public image endpoint
- `src/database/migrations/versions/j0e1f2a3b4c5_add_emoji_thumbnails.py`
- `tests/test_emoji_thumbnail_service.py`, `tests/test_emoji_thumbnail_endpoint.py`

**Backend — modify:**
- `src/database/models/__init__.py` — register `EmojiThumbnail`
- `src/database/services/emoji_placeholder_service.py` — add `referenced_emoji_ids()`
- `src/dashboard/routers/emoji_placeholders.py` — add `units` to the list response
- `src/dashboard/main.py` — mount the thumbnails router
- `tests/test_emoji_placeholders_api.py` — extend (units parsing)

**Frontend — create:**
- `frontend/src/shared/components/EmojiPreview.tsx`
- `frontend/src/shared/components/EmojiPreview.test.tsx`

**Frontend — modify:**
- `frontend/src/pages/EmojiPlaceholdersPage.tsx` — units interface + preview cell
- `frontend/src/pages/NotificationsPage.tsx` — units on placeholders + thumbnails in dropdown options

---

### Task 1: EmojiThumbnail model + migration

**Files:**
- Create: `src/database/models/emoji_thumbnail.py`
- Modify: `src/database/models/__init__.py`
- Create: `src/database/migrations/versions/j0e1f2a3b4c5_add_emoji_thumbnails.py`
- Test: `tests/test_emoji_thumbnail_service.py` (model smoke)

**Interfaces:**
- Produces: `EmojiThumbnail` model — `custom_emoji_id: str (PK)`, `data: bytes|None (LargeBinary)`, `mime: str|None`, `fetched_at: DateTime (server_default now, onupdate now)`.

- [ ] **Step 1: Write the model**

Create `src/database/models/emoji_thumbnail.py`:

```python
"""
EmojiThumbnail model — cached still thumbnail bytes for a Telegram custom
(premium) emoji, keyed by custom_emoji_id. `data` NULL = a fetch was attempted
but no image is available (negative cache; fetched_at marks the attempt time).
"""
from sqlalchemy import Column, DateTime, LargeBinary, String
from sqlalchemy.sql import func

from src.database.models.base import Base


class EmojiThumbnail(Base):
    """Global cache of custom-emoji thumbnail images."""

    __tablename__ = "emoji_thumbnails"

    custom_emoji_id = Column(String, primary_key=True)
    data = Column(LargeBinary, nullable=True)
    mime = Column(String, nullable=True)
    fetched_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2: Register the model**

In `src/database/models/__init__.py`, mirror the existing per-model import/`__all__` pattern (as `EmojiPlaceholder` was added):

```python
from src.database.models.emoji_thumbnail import EmojiThumbnail  # noqa: F401
```

and add `"EmojiThumbnail"` to `__all__` if that file maintains one.

- [ ] **Step 3: Write the migration**

Create `src/database/migrations/versions/j0e1f2a3b4c5_add_emoji_thumbnails.py`:

```python
"""add emoji_thumbnails cache table

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-06-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "j0e1f2a3b4c5"
down_revision = "i9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "emoji_thumbnails" not in inspector.get_table_names():
        op.create_table(
            "emoji_thumbnails",
            sa.Column("custom_emoji_id", sa.String(), primary_key=True),
            sa.Column("data", sa.LargeBinary(), nullable=True),
            sa.Column("mime", sa.String(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "emoji_thumbnails" in inspector.get_table_names():
        op.drop_table("emoji_thumbnails")
```

- [ ] **Step 4: Write a model smoke test**

Create `tests/test_emoji_thumbnail_service.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.emoji_thumbnail import EmojiThumbnail


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_model_stores_bytes():
    session = _session()
    row = EmojiThumbnail(custom_emoji_id="111", data=b"\x89PNG", mime="image/webp")
    session.add(row)
    session.commit()
    fetched = session.get(EmojiThumbnail, "111")
    assert fetched.data == b"\x89PNG"
    assert fetched.mime == "image/webp"
    assert fetched.fetched_at is not None
```

- [ ] **Step 5: Run the test**

Run: `pytest tests/test_emoji_thumbnail_service.py::test_model_stores_bytes -v`
Expected: PASS

- [ ] **Step 6: Verify migration parses + chains**

Run: `python3 -c "import ast; ast.parse(open('src/database/migrations/versions/j0e1f2a3b4c5_add_emoji_thumbnails.py').read()); print('ok')"`
Expected: `ok`. (Live `alembic upgrade head` requires PostgreSQL — note it as a human pre-merge step if no DB is available; verify `down_revision = "i9d0e1f2a3b4"` matches the current head by inspection.)

- [ ] **Step 7: Commit**

```bash
git add src/database/models/emoji_thumbnail.py src/database/models/__init__.py src/database/migrations/versions/j0e1f2a3b4c5_add_emoji_thumbnails.py tests/test_emoji_thumbnail_service.py
git commit -m "feat(emoji-thumb): add emoji_thumbnails cache model + migration"
```

---

### Task 2: EmojiThumbnailService + referenced_emoji_ids()

**Files:**
- Create: `src/database/services/emoji_thumbnail_service.py`
- Modify: `src/database/services/emoji_placeholder_service.py`
- Test: `tests/test_emoji_thumbnail_service.py` (extend)

**Interfaces:**
- Consumes: `EmojiThumbnail`, `EmojiPlaceholder`.
- Produces:
  - `EmojiThumbnailService(session)`: `get(id) -> EmojiThumbnail|None`, `store(id, data: bytes, mime: str) -> EmojiThumbnail`, `store_failure(id) -> EmojiThumbnail`, static `is_stale_failure(row) -> bool`. Module const `THUMBNAIL_NEGATIVE_TTL` (`timedelta(hours=1)`).
  - `EmojiPlaceholderService.referenced_emoji_ids() -> set[str]`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_emoji_thumbnail_service.py`:

```python
from datetime import datetime, timedelta, timezone

from src.database.services.emoji_thumbnail_service import (
    EmojiThumbnailService,
    THUMBNAIL_NEGATIVE_TTL,
)
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService


def test_store_and_get():
    session = _session()
    svc = EmojiThumbnailService(session)
    svc.store("111", b"img", "image/webp")
    row = svc.get("111")
    assert row.data == b"img"
    assert row.mime == "image/webp"


def test_store_failure_creates_null_row():
    session = _session()
    svc = EmojiThumbnailService(session)
    row = svc.store_failure("222")
    assert row.data is None
    assert svc.get("222") is not None


def test_is_stale_failure_boundary():
    # data present -> never stale
    present = EmojiThumbnail(custom_emoji_id="a", data=b"x", fetched_at=datetime.now(timezone.utc))
    assert EmojiThumbnailService.is_stale_failure(present) is False
    # fresh failure -> not stale
    fresh = EmojiThumbnail(custom_emoji_id="b", data=None, fetched_at=datetime.now(timezone.utc))
    assert EmojiThumbnailService.is_stale_failure(fresh) is False
    # old failure -> stale
    old = EmojiThumbnail(
        custom_emoji_id="c",
        data=None,
        fetched_at=datetime.now(timezone.utc) - THUMBNAIL_NEGATIVE_TTL - timedelta(minutes=1),
    )
    assert EmojiThumbnailService.is_stale_failure(old) is True


def test_referenced_emoji_ids():
    session = _session()
    psvc = EmojiPlaceholderService(session)
    pid = psvc.create("P")
    psvc.set_content(
        pid,
        [{"t": "emoji", "id": "111", "fb": "🔔"}, {"t": "text", "v": "hi"},
         {"t": "emoji", "id": "222", "fb": "🔥"}],
        raw_text="🔔hi🔥",
        set_by=None,
    )
    # An unconfigured placeholder contributes nothing.
    psvc.create("empty")
    assert psvc.referenced_emoji_ids() == {"111", "222"}
```

> Note: `EmojiThumbnail` is already imported at the top of this file from Task 1.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_emoji_thumbnail_service.py -v`
Expected: FAIL with `ModuleNotFoundError: ... emoji_thumbnail_service` (and `referenced_emoji_ids` AttributeError once the import resolves).

- [ ] **Step 3: Write the thumbnail service**

Create `src/database/services/emoji_thumbnail_service.py`:

```python
"""
EmojiThumbnailService — cache CRUD for custom-emoji thumbnails, plus a
negative-cache staleness check.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models.emoji_thumbnail import EmojiThumbnail

THUMBNAIL_NEGATIVE_TTL = timedelta(hours=1)


class EmojiThumbnailService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, custom_emoji_id: str) -> Optional[EmojiThumbnail]:
        return self.session.get(EmojiThumbnail, custom_emoji_id)

    def store(self, custom_emoji_id: str, data: bytes, mime: str) -> EmojiThumbnail:
        row = self.get(custom_emoji_id)
        if row is None:
            row = EmojiThumbnail(custom_emoji_id=custom_emoji_id)
            self.session.add(row)
        row.data = data
        row.mime = mime
        self.session.commit()
        self.session.refresh(row)
        return row

    def store_failure(self, custom_emoji_id: str) -> EmojiThumbnail:
        row = self.get(custom_emoji_id)
        if row is None:
            row = EmojiThumbnail(custom_emoji_id=custom_emoji_id)
            self.session.add(row)
        row.data = None
        row.mime = None
        self.session.commit()
        self.session.refresh(row)
        return row

    @staticmethod
    def is_stale_failure(row: EmojiThumbnail) -> bool:
        """True if this is a failure row (no data) older than the negative TTL."""
        if row.data is not None:
            return False
        fetched = row.fetched_at
        if fetched is None:
            return True
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - fetched > THUMBNAIL_NEGATIVE_TTL
```

- [ ] **Step 4: Add `referenced_emoji_ids` to EmojiPlaceholderService**

In `src/database/services/emoji_placeholder_service.py` (which already `import json` and imports `EmojiPlaceholder`), add this method to the class (in the queries section):

```python
    def referenced_emoji_ids(self) -> set:
        """All custom_emoji_ids referenced by any stored placeholder's content."""
        ids: set = set()
        for row in self.session.query(EmojiPlaceholder).all():
            if not row.content:
                continue
            for unit in json.loads(row.content):
                if unit.get("t") == "emoji" and unit.get("id"):
                    ids.add(str(unit["id"]))
        return ids
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_emoji_thumbnail_service.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add src/database/services/emoji_thumbnail_service.py src/database/services/emoji_placeholder_service.py tests/test_emoji_thumbnail_service.py
git commit -m "feat(emoji-thumb): thumbnail cache service + referenced_emoji_ids"
```

---

### Task 3: Thumbnail fetch helper + public image endpoint

**Files:**
- Create: `src/dashboard/routers/emoji_thumbnails.py`
- Modify: `src/dashboard/main.py`
- Test: `tests/test_emoji_thumbnail_endpoint.py`

**Interfaces:**
- Consumes: `EmojiThumbnailService`, `EmojiPlaceholderService`, `get_db`.
- Produces: module `src/dashboard/routers/emoji_thumbnails.py` with `fetch_thumbnail_bytes(bot, custom_emoji_id) -> tuple[bytes,str]|None`, `_get_bot() -> Bot|None`, and `GET /{custom_emoji_id}` (mounted at `/api/emoji-thumbnails`).

- [ ] **Step 1: Write failing tests**

Create `tests/test_emoji_thumbnail_endpoint.py`:

```python
import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models.base import Base
from src.dashboard.auth import get_db
from src.dashboard.routers import emoji_thumbnails
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService


@pytest.fixture
def ctx(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    # Seed a placeholder referencing emoji id "111".
    seed = Session()
    psvc = EmojiPlaceholderService(seed)
    pid = psvc.create("P")
    psvc.set_content(pid, [{"t": "emoji", "id": "111", "fb": "🔔"}], raw_text="🔔", set_by=None)
    seed.close()

    app = FastAPI()
    app.include_router(emoji_thumbnails.router, prefix="/api/emoji-thumbnails")

    def override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_db
    # Bot is non-None; fetch is mocked per-test.
    monkeypatch.setattr(emoji_thumbnails, "_get_bot", lambda: object())
    return TestClient(app), monkeypatch


def test_unknown_id_returns_404_without_fetch(ctx):
    client, monkeypatch = ctx
    fake = AsyncMock()
    monkeypatch.setattr(emoji_thumbnails, "fetch_thumbnail_bytes", fake)
    resp = client.get("/api/emoji-thumbnails/999")  # not referenced
    assert resp.status_code == 404
    fake.assert_not_called()


def test_fetch_then_cache_hit(ctx):
    client, monkeypatch = ctx
    fake = AsyncMock(return_value=(b"imgbytes", "image/webp"))
    monkeypatch.setattr(emoji_thumbnails, "fetch_thumbnail_bytes", fake)

    r1 = client.get("/api/emoji-thumbnails/111")
    assert r1.status_code == 200
    assert r1.content == b"imgbytes"
    assert r1.headers["content-type"] == "image/webp"

    r2 = client.get("/api/emoji-thumbnails/111")  # served from cache
    assert r2.status_code == 200
    assert r2.content == b"imgbytes"
    assert fake.call_count == 1  # not fetched again


def test_fetch_failure_negative_cached(ctx):
    client, monkeypatch = ctx
    fake = AsyncMock(return_value=None)
    monkeypatch.setattr(emoji_thumbnails, "fetch_thumbnail_bytes", fake)

    r1 = client.get("/api/emoji-thumbnails/111")
    assert r1.status_code == 404
    r2 = client.get("/api/emoji-thumbnails/111")  # fresh negative cache
    assert r2.status_code == 404
    assert fake.call_count == 1  # not retried while fresh


def test_fetch_helper_parses_sticker():
    bot = AsyncMock()
    bot.get_custom_emoji_stickers.return_value = [type("S", (), {"thumbnail": type("T", (), {"file_id": "fid"})()})()]
    tg_file = AsyncMock()
    tg_file.download_as_bytearray.return_value = bytearray(b"png")
    bot.get_file.return_value = tg_file

    data, mime = asyncio.get_event_loop().run_until_complete(
        emoji_thumbnails.fetch_thumbnail_bytes(bot, "111")
    )
    assert data == b"png"
    assert mime == "image/webp"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_emoji_thumbnail_endpoint.py -v`
Expected: FAIL with import error (`emoji_thumbnails` has no `router`/`fetch_thumbnail_bytes`).

- [ ] **Step 3: Write the router**

Create `src/dashboard/routers/emoji_thumbnails.py`:

```python
"""Public image endpoint serving cached Telegram custom-emoji thumbnails.

Thumbnails are non-sensitive (public emoji art), so the endpoint is
unauthenticated — but it only serves/fetches custom_emoji_ids referenced by a
stored placeholder, so it can't be used to make the server fetch arbitrary ids.
"""
import logging
import os
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from telegram import Bot

from src.dashboard.auth import get_db
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.emoji_thumbnail_service import EmojiThumbnailService

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}


def _get_bot() -> Optional[Bot]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; cannot fetch emoji thumbnails")
        return None
    try:
        return Bot(token=token)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to build Bot for thumbnails: {exc}", exc_info=True)
        return None


async def fetch_thumbnail_bytes(bot: Bot, custom_emoji_id: str) -> Optional[Tuple[bytes, str]]:
    """Download a custom emoji's static thumbnail. Returns (data, mime) or None."""
    stickers = await bot.get_custom_emoji_stickers([custom_emoji_id])
    if not stickers:
        return None
    thumb = stickers[0].thumbnail
    if thumb is None:
        return None
    tg_file = await bot.get_file(thumb.file_id)
    data = bytes(await tg_file.download_as_bytearray())
    return data, "image/webp"


@router.get("/{custom_emoji_id}")
async def get_emoji_thumbnail(custom_emoji_id: str, db: Session = Depends(get_db)):
    thumb_svc = EmojiThumbnailService(db)

    row = thumb_svc.get(custom_emoji_id)
    if row is not None and row.data is not None:
        return Response(content=row.data, media_type=row.mime or "image/webp", headers=_CACHE_HEADERS)

    # Abuse guard: never fetch ids not referenced by a stored placeholder.
    if custom_emoji_id not in EmojiPlaceholderService(db).referenced_emoji_ids():
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    # Fresh negative cache → don't re-hammer Telegram.
    if row is not None and not EmojiThumbnailService.is_stale_failure(row):
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    bot = _get_bot()
    if bot is None:
        thumb_svc.store_failure(custom_emoji_id)
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    try:
        result = await fetch_thumbnail_bytes(bot, custom_emoji_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Thumbnail fetch failed for {custom_emoji_id}: {exc}")
        result = None

    if result is None:
        thumb_svc.store_failure(custom_emoji_id)
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    data, mime = result
    thumb_svc.store(custom_emoji_id, data, mime)
    return Response(content=data, media_type=mime, headers=_CACHE_HEADERS)
```

- [ ] **Step 4: Mount the router**

In `src/dashboard/main.py`, add `emoji_thumbnails` to the `from src.dashboard.routers import (...)` block, then add near the other mounts:

```python
app.include_router(emoji_thumbnails.router, prefix="/api/emoji-thumbnails", tags=["emoji-thumbnails"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_emoji_thumbnail_endpoint.py -v`
Expected: PASS (all 4).

- [ ] **Step 6: Import + ruff + regression**

Run: `python3 -c "import src.dashboard.main"` (clean), `ruff check src/dashboard/routers/emoji_thumbnails.py` (clean), and `pytest -q` (compare to baseline; no NEW failures).

- [ ] **Step 7: Commit**

```bash
git add src/dashboard/routers/emoji_thumbnails.py src/dashboard/main.py tests/test_emoji_thumbnail_endpoint.py
git commit -m "feat(emoji-thumb): public lazy thumbnail image endpoint"
```

---

### Task 4: Add `units` to the placeholders list response

**Files:**
- Modify: `src/dashboard/routers/emoji_placeholders.py`
- Test: `tests/test_emoji_placeholders_api.py` (extend)

**Interfaces:**
- Produces: `EmojiPlaceholderResponse.units: list[EmojiUnit]` where `EmojiUnit = {type: str, value: str|None, emoji_id: str|None, fallback: str|None}`. Module helper `_parse_units(content: str|None) -> list[EmojiUnit]`.

- [ ] **Step 1: Write failing test**

Append to `tests/test_emoji_placeholders_api.py`:

```python
from src.dashboard.routers.emoji_placeholders import _parse_units, EmojiUnit


def test_parse_units_maps_emoji_and_text():
    import json
    content = json.dumps([
        {"t": "emoji", "id": "111", "fb": "🔔"},
        {"t": "text", "v": "THÔNG BÁO"},
    ])
    units = _parse_units(content)
    assert units == [
        EmojiUnit(type="emoji", emoji_id="111", fallback="🔔"),
        EmojiUnit(type="text", value="THÔNG BÁO"),
    ]


def test_parse_units_empty_for_unconfigured():
    assert _parse_units(None) == []
    assert _parse_units("") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_emoji_placeholders_api.py -v`
Expected: FAIL (`cannot import name '_parse_units'` / `EmojiUnit`).

- [ ] **Step 3: Add the schema + parser + wire into _to_response**

In `src/dashboard/routers/emoji_placeholders.py`, add `import json` at the top, add the `EmojiUnit` model, the `_parse_units` helper, the `units` field, and populate it in `_to_response`:

```python
import json
# ... existing imports ...

class EmojiUnit(BaseModel):
    type: str  # 'text' | 'emoji'
    value: Optional[str] = None
    emoji_id: Optional[str] = None
    fallback: Optional[str] = None


class EmojiPlaceholderResponse(BaseModel):
    id: int
    name: str
    configured: bool
    raw_text: Optional[str] = None
    units: List[EmojiUnit] = []

    @computed_field
    @property
    def token(self) -> str:
        return f"{{emo:{self.id}}}"


def _parse_units(content: Optional[str]) -> List[EmojiUnit]:
    if not content:
        return []
    out: List[EmojiUnit] = []
    for u in json.loads(content):
        if u.get("t") == "emoji":
            out.append(EmojiUnit(type="emoji", emoji_id=str(u.get("id")), fallback=u.get("fb", "")))
        else:
            out.append(EmojiUnit(type="text", value=u.get("v", "")))
    return out


def _to_response(row) -> EmojiPlaceholderResponse:
    return EmojiPlaceholderResponse(
        id=row.id,
        name=row.name,
        configured=bool(row.content),
        raw_text=row.raw_text,
        units=_parse_units(row.content),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_emoji_placeholders_api.py -v`
Expected: PASS

- [ ] **Step 5: Import + regression**

Run: `python3 -c "import src.dashboard.main"` clean; `ruff check src/dashboard/routers/emoji_placeholders.py` clean; `pytest -q` no NEW failures.

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/routers/emoji_placeholders.py tests/test_emoji_placeholders_api.py
git commit -m "feat(emoji-thumb): expose parsed units on placeholders list"
```

---

### Task 5: EmojiPreview frontend component

**Files:**
- Create: `frontend/src/shared/components/EmojiPreview.tsx`
- Test: `frontend/src/shared/components/EmojiPreview.test.tsx`

**Interfaces:**
- Consumes: `apiClient` (for `defaults.baseURL`).
- Produces: `EmojiPreview({ units })` + exported `EmojiUnit` type. Renders text units as `<span>`, emoji units as `<img src="{baseURL}/api/emoji-thumbnails/{emoji_id}">` with an `onError` fallback to the fallback char.

- [ ] **Step 1: Write failing test**

Create `frontend/src/shared/components/EmojiPreview.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EmojiPreview } from './EmojiPreview'

describe('EmojiPreview', () => {
  it('renders text spans and emoji images', () => {
    render(
      <EmojiPreview
        units={[
          { type: 'emoji', emoji_id: '111', fallback: '🔔' },
          { type: 'text', value: 'hello' },
        ]}
      />,
    )
    const img = screen.getByRole('img')
    expect(img.getAttribute('src')).toContain('/api/emoji-thumbnails/111')
    expect(img.getAttribute('alt')).toBe('🔔')
    expect(screen.getByText('hello')).toBeInTheDocument()
  })

  it('falls back to the fallback char when the image fails to load', () => {
    render(<EmojiPreview units={[{ type: 'emoji', emoji_id: '111', fallback: '🔔' }]} />)
    fireEvent.error(screen.getByRole('img'))
    expect(screen.getByText('🔔')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && CI=true npx vitest run src/shared/components/EmojiPreview.test.tsx`
Expected: FAIL (cannot resolve `./EmojiPreview`).

- [ ] **Step 3: Write the component**

Create `frontend/src/shared/components/EmojiPreview.tsx`:

```tsx
import { useState } from 'react'
import { apiClient } from '../lib/api'

export interface EmojiUnit {
  type: 'text' | 'emoji'
  value?: string | null
  emoji_id?: string | null
  fallback?: string | null
}

const API_BASE = apiClient.defaults.baseURL ?? ''

function EmojiImg({ emojiId, fallback }: { emojiId: string; fallback: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <span className="emoji-preview__fallback">{fallback}</span>
  return (
    <img
      src={`${API_BASE}/api/emoji-thumbnails/${emojiId}`}
      alt={fallback}
      className="emoji-preview__img"
      width={20}
      height={20}
      onError={() => setFailed(true)}
    />
  )
}

export function EmojiPreview({ units }: { units: EmojiUnit[] }) {
  return (
    <span className="emoji-preview">
      {units.map((u, i) =>
        u.type === 'emoji' && u.emoji_id ? (
          <EmojiImg key={i} emojiId={u.emoji_id} fallback={u.fallback ?? ''} />
        ) : (
          <span key={i}>{u.value ?? ''}</span>
        ),
      )}
    </span>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && CI=true npx vitest run src/shared/components/EmojiPreview.test.tsx`
Expected: PASS

- [ ] **Step 5: Build + lint**

Run: `cd frontend && npm run build` (succeeds) and `npx eslint src/shared/components/EmojiPreview.tsx` (clean).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/shared/components/EmojiPreview.tsx frontend/src/shared/components/EmojiPreview.test.tsx
git commit -m "feat(emoji-thumb): EmojiPreview component"
```

---

### Task 6: Render previews on the Emoji-placeholders page

**Files:**
- Modify: `frontend/src/pages/EmojiPlaceholdersPage.tsx`

**Interfaces:**
- Consumes: `EmojiPreview`, `EmojiUnit`; the list endpoint now returns `units`.

- [ ] **Step 1: Add `units` to the page's interface + import EmojiPreview**

In `frontend/src/pages/EmojiPlaceholdersPage.tsx`, import the component and extend the local interface:

```tsx
import { EmojiPreview, type EmojiUnit } from '../shared/components/EmojiPreview'

interface EmojiPlaceholder {
  id: number
  name: string
  configured: boolean
  raw_text: string | null
  token: string
  units: EmojiUnit[]
}
```

- [ ] **Step 2: Replace the preview cell to use EmojiPreview**

Replace the existing preview-cell block (currently rendering `raw_text` or the hint) with:

```tsx
<td className="emoji-placeholders-page__preview-cell">
  {item.configured && item.units && item.units.length > 0
    ? <EmojiPreview units={item.units} />
    : (
      <span
        className="emoji-placeholders-page__hint"
        title={t('emoji.setHint', 'Run /set_emo {id} in the bot and send your premium emoji').replace('{id}', String(item.id))}
      >
        — <em>{t('emoji.setHint', 'Run /set_emo {id} in the bot').replace('{id}', String(item.id))}</em>
      </span>
    )
  }
</td>
```

- [ ] **Step 3: Build + lint + test**

Run: `cd frontend && npm run build` (succeeds), `npx eslint src/pages/EmojiPlaceholdersPage.tsx` (clean), `CI=true npx vitest run` (all pass).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EmojiPlaceholdersPage.tsx
git commit -m "feat(emoji-thumb): show thumbnail previews on the Emoji page"
```

---

### Task 7: Thumbnails in notification header/footer dropdowns

**Files:**
- Modify: `frontend/src/pages/NotificationsPage.tsx`

**Interfaces:**
- Consumes: `EmojiPreview`, `EmojiUnit`; the placeholders the page already fetches now include `units`. Uses the `Select` option `icon` field (the component renders `opt.icon` before the label by default — no custom `renderOption` needed).

- [ ] **Step 1: Add `units` to the placeholder type + import EmojiPreview**

In `frontend/src/pages/NotificationsPage.tsx`, import the component and extend the `placeholders` state type to include `units`:

```tsx
import { EmojiPreview, type EmojiUnit } from '../shared/components/EmojiPreview'

// where placeholders state is typed:
const [placeholders, setPlaceholders] = useState<{ id: number; name: string; token: string; units: EmojiUnit[] }[]>([])
```

(Update the typed `apiClient.get<...>` call for `/api/emoji-placeholders` to the same shape.)

- [ ] **Step 2: Attach a preview icon to each option**

In the `placeholderOptions` construction, add an `icon` for configured placeholders (the "—" none option has none):

```tsx
const placeholderOptions = [
  { value: '', label: '—' },
  ...placeholders.map(p => ({
    value: String(p.id),
    label: `${p.name} (${p.token})`,
    icon: p.units && p.units.length > 0 ? <EmojiPreview units={p.units} /> : undefined,
  })),
]
```

(The two `<Select>` blocks already consume `placeholderOptions`; no further change needed — the default option renderer shows `opt.icon` then `opt.label`.)

- [ ] **Step 3: Build + lint + test**

Run: `cd frontend && npm run build` (succeeds), `npx eslint src/pages/NotificationsPage.tsx` (clean), `CI=true npx vitest run` (all pass).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/NotificationsPage.tsx
git commit -m "feat(emoji-thumb): thumbnail previews in notification dropdowns"
```

---

## Self-Review

**Spec coverage:**
- `emoji_thumbnail` cache table (bytes in DB, nullable data, fetched_at) → Task 1 ✓
- Service (get/store/store_failure/is_stale_failure, TTL) + `referenced_emoji_ids` → Task 2 ✓
- Async fetch helper (`getCustomEmojiStickers → getFile → download`) → Task 3 ✓
- Public image endpoint: cache hit, known-ids guard, fresh-negative skip, fetch→store, failure→404, missing token→404 → Task 3 ✓
- `units` on list response → Task 4 ✓
- `EmojiPreview` (text + `<img onError>` fallback) → Task 5 ✓
- Emoji page preview cell → Task 6 ✓
- Notification dropdown previews → Task 7 ✓
- Testing (service TTL/parse, endpoint guard/cache/fetch mocked, units parse, component render+fallback, SQLite + StaticPool, Telegram mocked) → Tasks 1–7 ✓
- Error handling (failure→negative cache→404→frontend fallback; unknown id no fetch) → Tasks 2,3,5 ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code.

**Type consistency:** unit shape `{"t":"emoji","id","fb"}` / `{"t":"text","v"}` (DB) → API `EmojiUnit{type,value,emoji_id,fallback}` (Task 4) → frontend `EmojiUnit` (Task 5) used identically in Tasks 6–7. `fetch_thumbnail_bytes`, `_get_bot`, `is_stale_failure`, `referenced_emoji_ids`, `THUMBNAIL_NEGATIVE_TTL`, `store`/`store_failure`/`get` names consistent across Tasks 2–3 and tests.

**Verification-required assumptions (flagged in tasks):** exact `models/__init__.py` register pattern (Task 1); that `get_db` is importable for the dependency override (Task 3 — it is, from `src.dashboard.auth`); the `Select` `icon` field renders before the label (Task 7 — confirmed from `Select.tsx` default render); live `alembic upgrade head` is a human pre-merge step (PostgreSQL-only).
