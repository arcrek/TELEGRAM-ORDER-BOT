# Block User Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins block users (by Telegram ID or username) so blocked users cannot create orders or top up, managed from a dashboard page and from `/block` / `/unblock` bot commands.

**Architecture:** A standalone `blocked_users` table is the source of truth — a row's existence *is* the block (no flag on `BotUser`, which resets `is_active` on `/start`). A `BlockService` provides `is_blocked` plus block/unblock/list. Four handler-level gates (bot order, bot topup ×2, public API order) call `is_blocked` before creating any order/topup. A FastAPI router + React page expose list/add/remove.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0 (sync service layer), Alembic, FastAPI + Pydantic, python-telegram-bot, React 18 + TypeScript + react-i18next, pytest (in-memory SQLite).

## Global Constraints

- Database access only through `src/database/services/` — never query models directly in handlers/routes.
- All bot handlers and dashboard routes are `async`; the DB **service layer is synchronous** (`self.session.query(...)`, `self.session.commit()`).
- Use the i18n system for all bot strings (`from src.bot.utils.language import t`); Vietnamese is the default locale and every key must exist in **both** `vi/bot.json` and `en/bot.json`.
- Every model change requires an Alembic migration; never modify tables directly. Postgres runs in UTC.
- Partial unique indexes must specify **both** `postgresql_where` and `sqlite_where` so they enforce on the migration-driven Postgres DB *and* the model-driven in-memory SQLite test DB.
- Every block gate passes **both** `telegram_user_id` and `username` to `is_blocked` (a username-only block row has `telegram_user_id = NULL`). Prefer the live Telegram username (`query.from_user.username` / `update.effective_user.username`) over the stored `BotUser.username`.
- Admin authorization for bot commands uses `is_admin(telegram_user_id)` from `src/bot/utils/admin_check.py`. Dashboard mutations use `require_admin_role`; listing uses `require_viewer_or_admin` (from `src/dashboard/auth.py`).
- Run `ruff check .` and `ruff format .` before each commit; run `pytest` for the touched test files.

---

### Task 1: `BlockedUser` model + Alembic migration

**Files:**
- Create: `src/database/models/blocked_users.py`
- Modify: `src/database/models/__init__.py` (register model)
- Create: `src/database/migrations/versions/k1f2a3b4c5d6_create_blocked_users_table.py`
- Test: `tests/test_blocked_user_model.py`

**Interfaces:**
- Produces: `BlockedUser` model with columns `id: int` (PK), `telegram_user_id: int | None`, `username: str | None`, `created_at: datetime`. Table name `blocked_users`. Two partial unique indexes: `ix_blocked_users_telegram_user_id` (where `telegram_user_id IS NOT NULL`) and `ix_blocked_users_username` (where `username IS NOT NULL`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_blocked_user_model.py`:

```python
"""Tests for the BlockedUser model and its partial unique indexes."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models.blocked_users import BlockedUser


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_block_by_id_and_by_username_coexist(db_session):
    db_session.add(BlockedUser(telegram_user_id=111))
    db_session.add(BlockedUser(username="alice"))
    db_session.commit()
    assert db_session.query(BlockedUser).count() == 2


def test_duplicate_telegram_id_violates_partial_unique(db_session):
    db_session.add(BlockedUser(telegram_user_id=222))
    db_session.commit()
    db_session.add(BlockedUser(telegram_user_id=222))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_username_violates_partial_unique(db_session):
    db_session.add(BlockedUser(username="bob"))
    db_session.commit()
    db_session.add(BlockedUser(username="bob"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_multiple_username_only_rows_do_not_collide_on_id_index(db_session):
    # Both have telegram_user_id = NULL; the partial index excludes NULLs.
    db_session.add(BlockedUser(username="carol"))
    db_session.add(BlockedUser(username="dave"))
    db_session.commit()
    assert db_session.query(BlockedUser).count() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_blocked_user_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.database.models.blocked_users'`.

- [ ] **Step 3: Create the model**

Create `src/database/models/blocked_users.py`:

```python
"""Blocked-user model — a row's existence blocks a Telegram id or username."""

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Index, text
from sqlalchemy.sql import func
from src.database.models.base import Base


class BlockedUser(Base):
    """A single block entry, keyed by either a Telegram id OR a username."""

    __tablename__ = "blocked_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, nullable=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_blocked_users_telegram_user_id",
            "telegram_user_id",
            unique=True,
            postgresql_where=text("telegram_user_id IS NOT NULL"),
            sqlite_where=text("telegram_user_id IS NOT NULL"),
        ),
        Index(
            "ix_blocked_users_username",
            "username",
            unique=True,
            postgresql_where=text("username IS NOT NULL"),
            sqlite_where=text("username IS NOT NULL"),
        ),
    )
```

- [ ] **Step 4: Register the model so metadata/migrations see it**

In `src/database/models/__init__.py`, add the import next to the other model imports (after the `bot_user` import line) and add `"BlockedUser"` to the `__all__` list:

```python
from src.database.models.blocked_users import BlockedUser  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_blocked_user_model.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Create the Alembic migration**

Create `src/database/migrations/versions/k1f2a3b4c5d6_create_blocked_users_table.py`:

```python
"""create blocked_users table

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-06-24 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k1f2a3b4c5d6"
down_revision: Union[str, None] = "j0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blocked_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_blocked_users_telegram_user_id",
        "blocked_users",
        ["telegram_user_id"],
        unique=True,
        postgresql_where=sa.text("telegram_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_blocked_users_username",
        "blocked_users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("username IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_blocked_users_username", table_name="blocked_users")
    op.drop_index(
        "ix_blocked_users_telegram_user_id", table_name="blocked_users"
    )
    op.drop_table("blocked_users")
```

- [ ] **Step 7: Verify the migration chain has a single head**

Run:
```bash
python3 - <<'EOF'
import os, re
d = "src/database/migrations/versions"
revs, downs = {}, set()
for f in os.listdir(d):
    if not f.endswith(".py") or f == "__init__.py":
        continue
    txt = open(os.path.join(d, f)).read()
    rm = re.search(r'^revision\s*[:=].*?["\']([^"\']+)["\']', txt, re.M)
    dm = re.search(r'^down_revision\s*[:=].*?["\']([^"\']+)["\']', txt, re.M)
    if rm:
        revs[rm.group(1)] = f
    if dm:
        downs.add(dm.group(1))
heads = [r for r in revs if r not in downs]
print("HEADS:", [(h, revs[h]) for h in heads])
assert heads == ["k1f2a3b4c5d6"], f"Expected single head k1f2a3b4c5d6, got {heads}"
print("OK: single head k1f2a3b4c5d6")
EOF
```
Expected: prints `OK: single head k1f2a3b4c5d6`. If a real Postgres is configured, optionally also run `alembic heads` and confirm it prints only `k1f2a3b4c5d6`.

- [ ] **Step 8: Lint and commit**

```bash
ruff check src/database/models/blocked_users.py src/database/migrations/versions/k1f2a3b4c5d6_create_blocked_users_table.py
ruff format src/database/models/blocked_users.py src/database/migrations/versions/k1f2a3b4c5d6_create_blocked_users_table.py
git add src/database/models/blocked_users.py src/database/models/__init__.py src/database/migrations/versions/k1f2a3b4c5d6_create_blocked_users_table.py tests/test_blocked_user_model.py
git commit -m "feat(block): add blocked_users model and migration"
```

---

### Task 2: `BlockService`

**Files:**
- Create: `src/database/services/block_service.py`
- Test: `tests/test_block_service.py`

**Interfaces:**
- Consumes: `BlockedUser` model from Task 1.
- Produces: `BlockService(session)` with:
  - `is_blocked(self, telegram_user_id: int | None, username: str | None) -> bool`
  - `block(self, identifier: str) -> BlockedUser` — parses id vs `@username`; idempotent (returns existing row if already blocked).
  - `unblock(self, identifier: str) -> bool` — True if a row was removed.
  - `add_block(self, *, telegram_user_id: int | None = None, username: str | None = None) -> BlockedUser` — idempotent; raises `ValueError` if neither provided.
  - `remove_block(self, block_id: int) -> bool`
  - `list_blocked(self, search: str | None = None, page: int = 1, per_page: int = 15) -> tuple[list[BlockedUser], int]`
  - `parse_identifier(identifier: str) -> tuple[int | None, str | None]` (static) — `("123") -> (123, None)`, `("@Bob") -> (None, "bob")`, `("bob") -> (None, "bob")`; raises `ValueError` on empty.

- [ ] **Step 1: Write the failing test**

Create `tests/test_block_service.py`:

```python
"""Tests for BlockService."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.services.block_service import BlockService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def svc(db_session):
    return BlockService(db_session)


def test_parse_identifier_numeric():
    assert BlockService.parse_identifier("123456") == (123456, None)


def test_parse_identifier_username_with_at():
    assert BlockService.parse_identifier("@Alice") == (None, "alice")


def test_parse_identifier_username_bare():
    assert BlockService.parse_identifier("Bob") == (None, "bob")


def test_parse_identifier_empty_raises():
    with pytest.raises(ValueError):
        BlockService.parse_identifier("   ")


def test_block_by_id_then_is_blocked(svc):
    svc.block("777")
    assert svc.is_blocked(777, None) is True
    assert svc.is_blocked(778, None) is False


def test_block_by_username_matches_case_insensitively(svc):
    svc.block("@Carol")
    assert svc.is_blocked(None, "carol") is True
    assert svc.is_blocked(None, "@CAROL") is True
    assert svc.is_blocked(999, None) is False


def test_is_blocked_matches_on_either_key(svc):
    svc.block("dave")  # username-only row
    # User whose id is unknown to us but username matches → blocked.
    assert svc.is_blocked(12345, "dave") is True


def test_is_blocked_false_when_no_identifiers(svc):
    assert svc.is_blocked(None, None) is False


def test_block_is_idempotent(svc):
    a = svc.block("555")
    b = svc.block("555")
    assert a.id == b.id
    items, total = svc.list_blocked()
    assert total == 1


def test_unblock_by_id(svc):
    svc.block("321")
    assert svc.unblock("321") is True
    assert svc.is_blocked(321, None) is False
    assert svc.unblock("321") is False  # already gone


def test_unblock_by_username(svc):
    svc.block("@erin")
    assert svc.unblock("Erin") is True
    assert svc.is_blocked(None, "erin") is False


def test_add_block_requires_an_identifier(svc):
    with pytest.raises(ValueError):
        svc.add_block()


def test_remove_block_by_id(svc):
    row = svc.block("404")
    assert svc.remove_block(row.id) is True
    assert svc.remove_block(row.id) is False


def test_list_blocked_search_and_pagination(svc):
    svc.block("100")
    svc.block("@frank")
    svc.block("@grace")
    items, total = svc.list_blocked(search="fra")
    assert total == 1
    assert items[0].username == "frank"
    items, total = svc.list_blocked()
    assert total == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_block_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.database.services.block_service'`.

- [ ] **Step 3: Implement the service**

Create `src/database/services/block_service.py`:

```python
"""Block service — manage the blocklist and check whether a user is blocked."""

from typing import Optional
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session
from src.database.models.blocked_users import BlockedUser


class BlockService:
    """Service for blocking/unblocking users and checking block status."""

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def parse_identifier(identifier: str) -> tuple[Optional[int], Optional[str]]:
        """Parse a raw identifier into (telegram_user_id, username).

        All-digits (optionally signed) → numeric id; otherwise a username
        (leading '@' stripped, lowercased). Raises ValueError if empty.
        """
        raw = (identifier or "").strip()
        if not raw:
            raise ValueError("Empty identifier")
        is_username = raw.startswith("@") or not raw.lstrip("-").lstrip("+").isdigit()
        if is_username:
            return None, raw.lstrip("@").lower()
        return int(raw), None

    def is_blocked(
        self, telegram_user_id: Optional[int], username: Optional[str]
    ) -> bool:
        """True if the id OR the (case-insensitive) username is blocked."""
        conditions = []
        if telegram_user_id is not None:
            conditions.append(BlockedUser.telegram_user_id == telegram_user_id)
        if username:
            conditions.append(
                func.lower(BlockedUser.username) == username.lstrip("@").lower()
            )
        if not conditions:
            return False
        return (
            self.session.query(BlockedUser.id).filter(or_(*conditions)).first()
            is not None
        )

    def add_block(
        self,
        *,
        telegram_user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> BlockedUser:
        """Create a block row (idempotent). Raises ValueError if no identifier."""
        if telegram_user_id is None and not username:
            raise ValueError("Must provide telegram_user_id or username")
        username_norm = username.lstrip("@").lower() if username else None

        existing = self.session.query(BlockedUser)
        if telegram_user_id is not None:
            existing = existing.filter(
                BlockedUser.telegram_user_id == telegram_user_id
            )
        else:
            existing = existing.filter(
                func.lower(BlockedUser.username) == username_norm
            )
        found = existing.first()
        if found:
            return found

        row = BlockedUser(telegram_user_id=telegram_user_id, username=username_norm)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def block(self, identifier: str) -> BlockedUser:
        """Parse a raw identifier and block it (idempotent)."""
        tid, uname = self.parse_identifier(identifier)
        return self.add_block(telegram_user_id=tid, username=uname)

    def remove_block(self, block_id: int) -> bool:
        """Remove a block by primary key. True if a row was deleted."""
        row = self.session.query(BlockedUser).filter_by(id=block_id).first()
        if not row:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def unblock(self, identifier: str) -> bool:
        """Parse a raw identifier and remove the matching block. True if removed."""
        tid, uname = self.parse_identifier(identifier)
        query = self.session.query(BlockedUser)
        if tid is not None:
            query = query.filter(BlockedUser.telegram_user_id == tid)
        else:
            query = query.filter(func.lower(BlockedUser.username) == uname)
        row = query.first()
        if not row:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def list_blocked(
        self,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 15,
    ) -> tuple[list[BlockedUser], int]:
        """Paginated list of block rows, newest first, optional substring search."""
        query = self.session.query(BlockedUser)
        if search:
            term = f"%{search.strip().lstrip('@').lower()}%"
            query = query.filter(
                or_(
                    func.lower(BlockedUser.username).like(term),
                    cast(BlockedUser.telegram_user_id, String).like(term),
                )
            )
        total = query.count()
        items = (
            query.order_by(BlockedUser.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_block_service.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Compile the list query against the Postgres dialect**

Run:
```bash
python3 -c "
from sqlalchemy import String, cast, func, or_
from sqlalchemy.dialects import postgresql
from src.database.models.blocked_users import BlockedUser
from sqlalchemy import select
term='%x%'
q = select(BlockedUser).where(or_(func.lower(BlockedUser.username).like(term), cast(BlockedUser.telegram_user_id, String).like(term)))
print(q.compile(dialect=postgresql.dialect()))
print('OK: compiles for postgresql')
"
```
Expected: prints SQL and `OK: compiles for postgresql` with no exception.

- [ ] **Step 6: Lint and commit**

```bash
ruff check src/database/services/block_service.py
ruff format src/database/services/block_service.py tests/test_block_service.py
git add src/database/services/block_service.py tests/test_block_service.py
git commit -m "feat(block): add BlockService"
```

---

### Task 3: Bot commands `/block` and `/unblock` + i18n

**Files:**
- Modify: `src/bot/handlers/commands.py` (add `block_command`, `unblock_command`)
- Modify: `src/bot/main.py` (register `CommandHandler`s)
- Modify: `src/i18n/locales/vi/bot.json` and `src/i18n/locales/en/bot.json`
- Test: `tests/test_block_commands.py`

**Interfaces:**
- Consumes: `BlockService` (Task 2), `is_admin` from `src/bot/utils/admin_check.py`, `t` from `src/bot/utils/language`, `get_session_factory`.
- Produces: `async def block_command(update, context)`, `async def unblock_command(update, context)`.

- [ ] **Step 1: Add i18n keys**

In `src/i18n/locales/vi/bot.json`, inside the `"commands"` object (next to `"setadmin"`), add:

```json
    "block": {
      "no_permission": "⛔ Bạn không có quyền dùng lệnh này.",
      "usage": "⚙️ Cách dùng:\n/block <id|@username> — Khóa người dùng\n/unblock <id|@username> — Mở khóa người dùng",
      "blocked": "✅ Đã khóa người dùng: {target}",
      "unblocked": "✅ Đã mở khóa người dùng: {target}",
      "not_blocked": "ℹ️ {target} hiện không bị khóa."
    },
```

In the same file, inside the existing `"errors"` object, add the blocked-order message:

```json
    "user_blocked": "⛔ Tài khoản của bạn đã bị khóa nên không thể tạo đơn hàng hoặc nạp tiền. Vui lòng liên hệ admin để được hỗ trợ."
```

In `src/i18n/locales/en/bot.json`, inside `"commands"`, add:

```json
    "block": {
      "no_permission": "⛔ You do not have permission to use this command.",
      "usage": "⚙️ Usage:\n/block <id|@username> — Block a user\n/unblock <id|@username> — Unblock a user",
      "blocked": "✅ Blocked user: {target}",
      "unblocked": "✅ Unblocked user: {target}",
      "not_blocked": "ℹ️ {target} is not currently blocked."
    },
```

And inside the `"errors"` object in `en/bot.json`:

```json
    "user_blocked": "⛔ Your account is blocked and cannot create orders or top up. Please contact an admin for help."
```

> **Implementer note:** these JSON files are also loaded by the dashboard build only if referenced; here they are bot locales. Validate JSON after editing: `python3 -c "import json; json.load(open('src/i18n/locales/vi/bot.json')); json.load(open('src/i18n/locales/en/bot.json')); print('valid')"`. Mind trailing commas.

- [ ] **Step 2: Write the failing test**

Create `tests/test_block_commands.py`:

```python
"""Tests for /block and /unblock command handlers."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.services.block_service import BlockService


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _make_update(text_args):
    update = MagicMock()
    update.effective_user.id = 42
    update.message.reply_text = AsyncMock()
    return update


def _make_context(args):
    context = MagicMock()
    context.args = args
    return context


def test_block_command_rejects_non_admin(session_factory):
    from src.bot.handlers import commands
    update = _make_update([])
    context = _make_context(["123"])
    with patch.object(commands, "is_admin", return_value=False):
        asyncio.run(commands.block_command(update, context))
    update.message.reply_text.assert_awaited_once()
    # No block created: factory never used because we patched is_admin off.


def test_block_command_blocks_id_for_admin(session_factory):
    from src.bot.handlers import commands
    update = _make_update([])
    context = _make_context(["123"])
    with patch.object(commands, "is_admin", return_value=True), patch.object(
        commands, "get_session_factory", return_value=session_factory
    ):
        asyncio.run(commands.block_command(update, context))
    update.message.reply_text.assert_awaited_once()
    # Verify the block landed.
    svc = BlockService(session_factory())
    assert svc.is_blocked(123, None) is True


def test_block_command_usage_when_no_args(session_factory):
    from src.bot.handlers import commands
    update = _make_update([])
    context = _make_context([])
    with patch.object(commands, "is_admin", return_value=True), patch.object(
        commands, "get_session_factory", return_value=session_factory
    ):
        asyncio.run(commands.block_command(update, context))
    update.message.reply_text.assert_awaited_once()


def test_unblock_command_removes_block(session_factory):
    from src.bot.handlers import commands
    # Seed a block first.
    BlockService(session_factory()).block("123")
    update = _make_update([])
    context = _make_context(["123"])
    with patch.object(commands, "is_admin", return_value=True), patch.object(
        commands, "get_session_factory", return_value=session_factory
    ):
        asyncio.run(commands.unblock_command(update, context))
    update.message.reply_text.assert_awaited_once()
    assert BlockService(session_factory()).is_blocked(123, None) is False
```

> **Note:** `conftest.py` auto-patches the language DB so `t()` works without a real DB in these unit tests (they don't use the `db_session` fixture name).

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_block_commands.py -v`
Expected: FAIL — `AttributeError: module 'src.bot.handlers.commands' has no attribute 'block_command'`.

- [ ] **Step 4: Implement the command handlers**

In `src/bot/handlers/commands.py`, add an import for `BlockService` at the top with the other service imports:

```python
from src.database.services.block_service import BlockService
```

Then add these two handlers (e.g. after `setadmin_command`):

```python
async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /block <id|@username> — block a user (admin only)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text(t("commands.block.no_permission", update))
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(t("commands.block.usage", update))
        return

    identifier = args[0]
    session_factory = get_session_factory()
    session = session_factory()
    try:
        try:
            BlockService(session).block(identifier)
        except ValueError:
            await update.message.reply_text(t("commands.block.usage", update))
            return
    finally:
        session.close()
    await update.message.reply_text(
        t("commands.block.blocked", update, target=identifier)
    )


async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unblock <id|@username> — unblock a user (admin only)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text(t("commands.block.no_permission", update))
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(t("commands.block.usage", update))
        return

    identifier = args[0]
    session_factory = get_session_factory()
    session = session_factory()
    try:
        try:
            removed = BlockService(session).unblock(identifier)
        except ValueError:
            await update.message.reply_text(t("commands.block.usage", update))
            return
    finally:
        session.close()
    if removed:
        await update.message.reply_text(
            t("commands.block.unblocked", update, target=identifier)
        )
    else:
        await update.message.reply_text(
            t("commands.block.not_blocked", update, target=identifier)
        )
```

- [ ] **Step 5: Register the handlers**

In `src/bot/main.py`, add `block_command, unblock_command` to the import from `src.bot.handlers.commands` (the import block at lines 10-25), and register them next to `setadmin` (after line 125):

```python
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("unblock", unblock_command))
```

- [ ] **Step 6: Run tests + validate JSON**

```bash
python3 -c "import json; json.load(open('src/i18n/locales/vi/bot.json')); json.load(open('src/i18n/locales/en/bot.json')); print('json valid')"
pytest tests/test_block_commands.py -v
```
Expected: `json valid`; all command tests PASS.

- [ ] **Step 7: Lint and commit**

```bash
ruff check src/bot/handlers/commands.py src/bot/main.py
ruff format src/bot/handlers/commands.py src/bot/main.py tests/test_block_commands.py
git add src/bot/handlers/commands.py src/bot/main.py src/i18n/locales/vi/bot.json src/i18n/locales/en/bot.json tests/test_block_commands.py
git commit -m "feat(block): add /block and /unblock bot commands"
```

---

### Task 4: Gate bot order creation (`handle_payment`)

**Files:**
- Modify: `src/bot/handlers/callbacks.py` (`handle_payment`)
- Test: `tests/test_block_order_gate.py`

**Interfaces:**
- Consumes: `BlockService.is_blocked` (Task 2), `errors.user_blocked` i18n key (Task 3).

- [ ] **Step 1: Write the failing test**

Create `tests/test_block_order_gate.py`:

```python
"""A blocked user is rejected at the bot payment step before an order is created."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.services.block_service import BlockService


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_blocked_user_cannot_create_order(session_factory):
    from src.bot.handlers import callbacks
    # Block user 500 by id.
    BlockService(session_factory()).block("500")

    query = MagicMock()
    query.data = "payment_var_1"
    query.from_user.id = 500
    query.from_user.username = None
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query

    # Provide a valid user_state so we get past the early state guards.
    state = MagicMock()
    state.selected_variation_id = "var_1"
    state.quantity = 1

    with patch.object(callbacks, "get_session_factory", return_value=session_factory), \
         patch.object(callbacks.state_manager, "get_user_state", return_value=state), \
         patch("src.database.services.order_service.OrderService.create_order") as create_order:
        asyncio.run(callbacks.handle_payment(update, MagicMock()))

    create_order.assert_not_called()
    query.edit_message_text.assert_awaited()  # block message shown


def test_blocked_by_username_cannot_create_order(session_factory):
    from src.bot.handlers import callbacks
    BlockService(session_factory()).block("@ghost")

    query = MagicMock()
    query.data = "payment_var_1"
    query.from_user.id = 999  # id NOT in blocklist
    query.from_user.username = "Ghost"  # username IS blocked
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query

    state = MagicMock()
    state.selected_variation_id = "var_1"
    state.quantity = 1

    with patch.object(callbacks, "get_session_factory", return_value=session_factory), \
         patch.object(callbacks.state_manager, "get_user_state", return_value=state), \
         patch("src.database.services.order_service.OrderService.create_order") as create_order:
        asyncio.run(callbacks.handle_payment(update, MagicMock()))

    create_order.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_block_order_gate.py -v`
Expected: FAIL — `create_order` IS called (no gate yet), so `assert_not_called()` fails.

- [ ] **Step 3: Add the fail-fast gate**

In `src/bot/handlers/callbacks.py`, inside `handle_payment`, immediately after the session is opened (right after `session = session_factory()` at ~line 858, inside the `try:` block before the `order_service = OrderService(session)` line), add:

```python
        # Block gate: a blocked user cannot create an order.
        from src.database.services.block_service import BlockService
        from src.bot.utils.language import t as _t

        if BlockService(session).is_blocked(user_id, query.from_user.username):
            await query.edit_message_text(_t("errors.user_blocked", update))
            return
```

> **Placement:** this must come *before* the variation/stock/bonus lookups so a blocked user sees the block message rather than "insufficient stock". `user_id` is already defined above (`user_id = query.from_user.id`). The `return` inside the `try` still runs the `finally: session.close()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_block_order_gate.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Lint and commit**

```bash
ruff check src/bot/handlers/callbacks.py
ruff format src/bot/handlers/callbacks.py tests/test_block_order_gate.py
git add src/bot/handlers/callbacks.py tests/test_block_order_gate.py
git commit -m "feat(block): gate bot order creation for blocked users"
```

---

### Task 5: Gate bot topup creation (both paths)

**Files:**
- Modify: `src/bot/handlers/balance.py` (`handle_balance_topup_amount`, `handle_topup_amount_text`)
- Test: `tests/test_block_topup_gate.py`

**Interfaces:**
- Consumes: `BlockService.is_blocked` (Task 2), `errors.user_blocked` i18n key (Task 3).

- [ ] **Step 1: Write the failing test**

Create `tests/test_block_topup_gate.py`:

```python
"""A blocked user cannot create a topup via either preset or custom path."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models.bot_user import BotUser
from src.database.services.block_service import BlockService


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_user(session_factory, telegram_id, username=None):
    s = session_factory()
    s.add(BotUser(telegram_user_id=telegram_id, username=username, has_started=True))
    s.commit()
    s.close()


def test_blocked_user_preset_topup_rejected(session_factory):
    from src.bot.handlers import balance
    _seed_user(session_factory, 600, "blockeduser")
    BlockService(session_factory()).block("600")

    query = MagicMock()
    query.data = "topup_amount_50000"
    query.from_user.id = 600
    query.from_user.username = "blockeduser"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.message_id = 1
    update = MagicMock()
    update.callback_query = query

    with patch.object(balance, "get_session_factory", return_value=session_factory), \
         patch("src.database.services.topup_service.TopupService.create_topup") as create_topup, \
         patch.object(balance, "_create_topup_qr", new=AsyncMock()):
        asyncio.run(balance.handle_balance_topup_amount(update, MagicMock()))

    create_topup.assert_not_called()
    query.edit_message_text.assert_awaited()


def test_blocked_user_custom_topup_rejected(session_factory):
    from src.bot.handlers import balance
    from src.bot.states.state_manager import UserState
    _seed_user(session_factory, 601)
    BlockService(session_factory()).block("601")

    update = MagicMock()
    update.message.text = "50000"
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 601
    update.effective_user.username = None

    state = UserState()
    state.awaiting_topup_amount = True

    with patch.object(balance, "get_session_factory", return_value=session_factory), \
         patch.object(balance.state_manager, "get_user_state", return_value=state), \
         patch.object(balance.state_manager, "set_user_state"), \
         patch("src.database.services.topup_service.TopupService.create_topup") as create_topup, \
         patch.object(balance, "_create_topup_qr", new=AsyncMock()):
        asyncio.run(balance.handle_topup_amount_text(update, MagicMock()))

    create_topup.assert_not_called()
    update.message.reply_text.assert_awaited()
```

> **Implementer note:** confirm `state_manager` is importable as `balance.state_manager` in `src/bot/handlers/balance.py`; if it is imported under a different name, patch that name. Confirm `_create_topup_qr` and `_get_bot_user` exist in that module (they do per the current code).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_block_topup_gate.py -v`
Expected: FAIL — `create_topup` called (no gate yet).

- [ ] **Step 3: Add the gate to the preset path**

In `src/bot/handlers/balance.py`, in `handle_balance_topup_amount`, right after the `bot_user` is fetched and the `if not bot_user:` guard (after ~line 515), add:

```python
        from src.database.services.block_service import BlockService

        if BlockService(session).is_blocked(
            bot_user.telegram_user_id, query.from_user.username or bot_user.username
        ):
            await query.edit_message_text(t("errors.user_blocked", update))
            return
```

- [ ] **Step 4: Add the gate to the custom path**

In the same file, in `handle_topup_amount_text`, after the `bot_user` fetch and `if not bot_user:` guard (after ~line 609), add:

```python
        from src.database.services.block_service import BlockService

        if BlockService(session).is_blocked(
            bot_user.telegram_user_id,
            update.effective_user.username or bot_user.username,
        ):
            await update.message.reply_text(t("errors.user_blocked", update))
            return
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_block_topup_gate.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Lint and commit**

```bash
ruff check src/bot/handlers/balance.py
ruff format src/bot/handlers/balance.py tests/test_block_topup_gate.py
git add src/bot/handlers/balance.py tests/test_block_topup_gate.py
git commit -m "feat(block): gate bot topup creation for blocked users"
```

---

### Task 6: Gate public API v1 order creation

**Files:**
- Modify: `src/dashboard/routers/api_v1.py` (`create_order` endpoint)
- Test: `tests/test_block_api_gate.py`

**Interfaces:**
- Consumes: `BlockService.is_blocked` (Task 2). `current_user: BotUser` is already resolved by `get_api_user`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_block_api_gate.py`:

```python
"""A blocked user's API token cannot create an order (HTTP 403)."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models.bot_user import BotUser
from src.database.services.block_service import BlockService
from src.dashboard.main import app
from src.dashboard.auth import get_db


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    # Seed a user with an API token, then block them.
    s = TestingSession()
    s.add(BotUser(telegram_user_id=700, username="apiuser", api_token="tok-123", has_started=True))
    s.commit()
    s.close()
    BlockService(TestingSession()).block("700")

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_blocked_user_order_returns_403(client):
    resp = client.post(
        "/api/v1/orders",
        headers={"Authorization": "Bearer tok-123"},
        json={"variation_id": "whatever", "quantity": 1},
    )
    assert resp.status_code == 403
```

> **Implementer note:** if the `slowapi` rate limiter interferes with `TestClient`, the request still returns before hitting it because the gate is the first statement. If import-time config (e.g. `CORS_ORIGINS`) is required, the test inherits the app's defaults — no extra env needed for a 403 path. If `ApiOrderRequest` requires other fields, add them to the JSON body with dummy values; the gate fires before validation of `variation_id` existence.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_block_api_gate.py -v`
Expected: FAIL — returns 422 (variation not found) or 200, not 403.

- [ ] **Step 3: Add the gate**

In `src/dashboard/routers/api_v1.py`, as the **first** statement inside the `create_order` function body (right after the docstring, before `variation_id = payload.variation_id`), add:

```python
    from src.database.services.block_service import BlockService

    if BlockService(db).is_blocked(
        current_user.telegram_user_id, current_user.username
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is blocked and cannot create orders.",
        )
```

> `status` and `HTTPException` are already imported in this module (used elsewhere in the endpoint).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_block_api_gate.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
ruff check src/dashboard/routers/api_v1.py
ruff format src/dashboard/routers/api_v1.py tests/test_block_api_gate.py
git add src/dashboard/routers/api_v1.py tests/test_block_api_gate.py
git commit -m "feat(block): gate public API order creation for blocked users"
```

---

### Task 7: Dashboard router `/api/blocked-users`

**Files:**
- Create: `src/dashboard/routers/blocked_users.py`
- Modify: `src/dashboard/main.py` (import + `include_router`)
- Test: `tests/test_blocked_users_router.py`

**Interfaces:**
- Consumes: `BlockService` (Task 2); auth deps `get_db`, `require_admin_role`, `require_viewer_or_admin`.
- Produces: routes
  - `GET /api/blocked-users` → `{items: [...], total, page, per_page, total_pages}` where each item is `{id, telegram_user_id, username, created_at}`.
  - `POST /api/blocked-users` body `{identifier: str}` → the created block row; 400 on empty identifier.
  - `DELETE /api/blocked-users/{block_id}` → `{success: bool}`; 404 if not found.

- [ ] **Step 1: Write the failing test**

Create `tests/test_blocked_users_router.py`:

```python
"""Tests for the blocked-users dashboard router."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.dashboard.main import app
from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # Bypass auth in tests.
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_role] = lambda: object()
    app.dependency_overrides[require_viewer_or_admin] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_add_list_and_delete_block(client):
    # Add by id.
    r = client.post("/api/blocked-users", json={"identifier": "12345"})
    assert r.status_code == 200, r.text
    block_id = r.json()["id"]
    assert r.json()["telegram_user_id"] == 12345

    # Add by username.
    r2 = client.post("/api/blocked-users", json={"identifier": "@SomeUser"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "someuser"

    # List shows both.
    r3 = client.get("/api/blocked-users")
    assert r3.status_code == 200
    assert r3.json()["total"] == 2

    # Search by username substring.
    r4 = client.get("/api/blocked-users", params={"search": "some"})
    assert r4.json()["total"] == 1

    # Delete the first.
    r5 = client.delete(f"/api/blocked-users/{block_id}")
    assert r5.status_code == 200
    assert r5.json()["success"] is True

    # Deleting again → 404.
    r6 = client.delete(f"/api/blocked-users/{block_id}")
    assert r6.status_code == 404


def test_add_block_empty_identifier_returns_400(client):
    r = client.post("/api/blocked-users", json={"identifier": "   "})
    assert r.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_blocked_users_router.py -v`
Expected: FAIL — 404 for all routes (router not mounted yet).

- [ ] **Step 3: Implement the router**

Create `src/dashboard/routers/blocked_users.py`:

```python
"""Blocked-users router — admin management of the user blocklist."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.services.block_service import BlockService


router = APIRouter()


class BlockedUserRow(BaseModel):
    id: int
    telegram_user_id: Optional[int]
    username: Optional[str]
    created_at: datetime


class BlockedUserListResponse(BaseModel):
    items: list[BlockedUserRow]
    total: int
    page: int
    per_page: int
    total_pages: int


class AddBlockRequest(BaseModel):
    identifier: str


class DeleteBlockResponse(BaseModel):
    success: bool


@router.get("", response_model=BlockedUserListResponse, include_in_schema=True)
@router.get("/", response_model=BlockedUserListResponse, include_in_schema=False)
async def list_blocked_users(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin=Depends(require_viewer_or_admin),
):
    items, total = BlockService(db).list_blocked(
        search=search, page=page, per_page=per_page
    )
    return BlockedUserListResponse(
        items=[
            BlockedUserRow(
                id=row.id,
                telegram_user_id=row.telegram_user_id,
                username=row.username,
                created_at=row.created_at,
            )
            for row in items
        ],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
    )


@router.post("", response_model=BlockedUserRow, include_in_schema=True)
@router.post("/", response_model=BlockedUserRow, include_in_schema=False)
async def add_blocked_user(
    payload: AddBlockRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    try:
        row = BlockService(db).block(payload.identifier)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifier is required")
    return BlockedUserRow(
        id=row.id,
        telegram_user_id=row.telegram_user_id,
        username=row.username,
        created_at=row.created_at,
    )


@router.delete("/{block_id}", response_model=DeleteBlockResponse)
async def delete_blocked_user(
    block_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    removed = BlockService(db).remove_block(block_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Block not found")
    return DeleteBlockResponse(success=True)
```

- [ ] **Step 4: Mount the router**

In `src/dashboard/main.py`, add `blocked_users` to the router import block (lines 16-35):

```python
    blocked_users,
```

and add an `include_router` line near the `balances` one (after line 117):

```python
app.include_router(
    blocked_users.router, prefix="/api/blocked-users", tags=["blocked-users"]
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_blocked_users_router.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Lint and commit**

```bash
ruff check src/dashboard/routers/blocked_users.py src/dashboard/main.py
ruff format src/dashboard/routers/blocked_users.py src/dashboard/main.py tests/test_blocked_users_router.py
git add src/dashboard/routers/blocked_users.py src/dashboard/main.py tests/test_blocked_users_router.py
git commit -m "feat(block): add /api/blocked-users dashboard router"
```

---

### Task 8: Frontend Blocked Users page

**Files:**
- Create: `frontend/src/pages/BlockedUsersPage.tsx`
- Modify: `frontend/src/app/routes.ts` (add route)
- Modify: `frontend/src/App.tsx` (import + `<Route>`)
- Modify: `frontend/src/app/layouts/Sidebar.tsx` (add `Ban` to `ICON_MAP` + import)
- Modify: `frontend/src/i18n/locales/vi/nav.json` and `frontend/src/i18n/locales/en/nav.json` (nav label)

**Interfaces:**
- Consumes: `GET/POST/DELETE /api/blocked-users` (Task 7), `apiClient`, `formatApiError`, shared components (`PageHeader`, `Table`, `Pagination`, `Input`, `IconButton`, `Button`), `useConfirm`, `useToast`.

- [ ] **Step 1: Add the route definition**

In `frontend/src/app/routes.ts`, add to the `operations` group (after the `balances` entry, line 26):

```typescript
  { path: '/blocked-users', key: 'blockedUsers', labelKey: 'nav.blockedUsers', group: 'operations', iconName: 'Ban' },
```

- [ ] **Step 2: Add the nav labels**

In `frontend/src/i18n/locales/vi/nav.json`, inside the `"nav"` object, add:

```json
    "blockedUsers": "Người dùng bị khóa",
```

In `frontend/src/i18n/locales/en/nav.json`, inside the `"nav"` object, add:

```json
    "blockedUsers": "Blocked Users",
```

- [ ] **Step 3: Register the icon**

In `frontend/src/app/layouts/Sidebar.tsx`, add `Ban` to the lucide-react import (lines 4-8) and to the `ICON_MAP` object (lines 13-16):

```typescript
// import line — add Ban:
  Bot, PanelLeftClose, PanelLeft, Ban,
// ICON_MAP — add Ban:
  Upload, Database, Gift, Settings, Users, Boxes, Wallet, BookOpen, Smile, Ban,
```

- [ ] **Step 4: Create the page**

Create `frontend/src/pages/BlockedUsersPage.tsx`:

```tsx
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Ban, RefreshCw, Trash2, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../shared/components/PageHeader'
import { Table, type ColumnDef } from '../shared/components/Table'
import { Pagination } from '../shared/components/Pagination'
import { IconButton } from '../shared/components/IconButton'
import { Button } from '../shared/components/Button'
import { Input } from '../shared/components/Input'
import { Tooltip } from '../shared/components/Tooltip'
import { useConfirm } from '../shared/components/ConfirmDialog'
import { useToast } from '../shared/components/Toast'
import { apiClient, formatApiError } from '../shared/lib/api'
import { useFormat } from '../shared/lib/format'

interface BlockedUserRow {
  id: number
  telegram_user_id: number | null
  username: string | null
  created_at: string
}

interface BlockedListResponse {
  items: BlockedUserRow[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export function BlockedUsersPage() {
  const { t } = useTranslation()
  const fmt = useFormat()
  const confirm = useConfirm()
  const toast = useToast()

  const [searchParams, setSearchParams] = useSearchParams()
  const urlSearch = searchParams.get('q') ?? ''
  const urlPage = Math.max(1, Number(searchParams.get('page') ?? '1'))

  const setParam = useCallback(
    (updates: Record<string, string | null>) => {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(updates)) {
          if (v === null || v === '') next.delete(k)
          else next.set(k, v)
        }
        return next
      }, { replace: true })
    },
    [setSearchParams],
  )

  const [searchInput, setSearchInput] = useState(urlSearch)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => { setSearchInput(urlSearch) }, [urlSearch])
  const handleSearchChange = (val: string) => {
    setSearchInput(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setParam({ q: val || null, page: null }), 300)
  }

  const [rows, setRows] = useState<BlockedUserRow[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [perPage, setPerPage] = useState(15)
  const [addValue, setAddValue] = useState('')
  const [adding, setAdding] = useState(false)

  const fetchRows = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = { page: String(urlPage), per_page: String(perPage) }
      if (urlSearch) params.search = urlSearch
      const res = await apiClient.get<BlockedListResponse>('/api/blocked-users', { params })
      setRows(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      setError(formatApiError(err, t('blockedUsers.loadError', 'Không thể tải danh sách')))
    } finally {
      setLoading(false)
    }
  }, [urlPage, perPage, urlSearch, t])

  useEffect(() => { fetchRows() }, [fetchRows])

  const handleAdd = useCallback(async () => {
    const identifier = addValue.trim()
    if (!identifier) return
    setAdding(true)
    try {
      await apiClient.post('/api/blocked-users', { identifier })
      setAddValue('')
      toast.success(t('blockedUsers.added', 'Đã khóa người dùng'))
      setParam({ page: null })
      fetchRows()
    } catch (err) {
      toast.error(formatApiError(err, t('blockedUsers.addError', 'Không thể khóa người dùng')))
    } finally {
      setAdding(false)
    }
  }, [addValue, t, toast, setParam, fetchRows])

  const handleRemove = useCallback(async (row: BlockedUserRow) => {
    const label = row.username ? `@${row.username}` : String(row.telegram_user_id)
    const ok = await confirm({
      title: t('blockedUsers.confirmTitle', 'Mở khóa người dùng?'),
      message: t('blockedUsers.confirmMessage', { defaultValue: 'Bỏ khóa {{label}}?', label }),
    })
    if (!ok) return
    try {
      await apiClient.delete(`/api/blocked-users/${row.id}`)
      toast.success(t('blockedUsers.removed', 'Đã mở khóa'))
      fetchRows()
    } catch (err) {
      toast.error(formatApiError(err, t('blockedUsers.removeError', 'Không thể mở khóa')))
    }
  }, [confirm, t, toast, fetchRows])

  const columns = useMemo<ColumnDef<BlockedUserRow>[]>(() => [
    {
      id: 'identifier',
      header: t('blockedUsers.colIdentifier', 'Người dùng'),
      cell: row => row.username
        ? <span style={{ color: 'var(--brand-500)', fontWeight: 500 }}>@{row.username}</span>
        : <span style={{ fontFamily: 'monospace' }}>{row.telegram_user_id}</span>,
    },
    {
      id: 'type',
      header: t('blockedUsers.colType', 'Loại'),
      width: 140,
      cell: row => row.username
        ? t('blockedUsers.typeUsername', 'Username')
        : t('blockedUsers.typeId', 'Telegram ID'),
    },
    {
      id: 'created_at',
      header: t('blockedUsers.colBlockedAt', 'Thời gian khóa'),
      width: 180,
      cell: row => row.created_at ? fmt.dateTime(row.created_at) : '—',
    },
    {
      id: 'actions',
      header: '',
      width: 64,
      align: 'right',
      cell: row => (
        <Tooltip content={t('blockedUsers.unblock', 'Mở khóa')}>
          <IconButton
            icon={<Trash2 size={14} />}
            aria-label={t('blockedUsers.unblock', 'Mở khóa')}
            size="sm"
            variant="ghost"
            onClick={e => { e.stopPropagation(); handleRemove(row) }}
          />
        </Tooltip>
      ),
    },
  ], [t, fmt, handleRemove])

  return (
    <div className="blocked-users-page">
      <PageHeader
        title={t('nav.blockedUsers', 'Người dùng bị khóa')}
        description={t('blockedUsers.description', 'Người dùng bị khóa không thể tạo đơn hàng hoặc nạp tiền')}
        actions={
          <IconButton
            icon={<RefreshCw size={14} />}
            aria-label={t('common.refresh', 'Làm mới')}
            variant="ghost"
            size="sm"
            onClick={fetchRows}
          />
        }
      />

      {/* Add block */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Input
          placeholder={t('blockedUsers.addPlaceholder', 'Nhập Telegram ID hoặc @username...')}
          value={addValue}
          size="sm"
          onChange={e => setAddValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleAdd() }}
          style={{ minWidth: 280 }}
        />
        <Button
          size="sm"
          leftIcon={<Plus size={14} />}
          onClick={handleAdd}
          disabled={adding || !addValue.trim()}
        >
          {t('blockedUsers.addButton', 'Khóa')}
        </Button>
      </div>

      {/* Search */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Input
          leftIcon={<Search size={14} />}
          placeholder={t('blockedUsers.searchPlaceholder', 'Tìm theo username hoặc Telegram ID...')}
          value={searchInput}
          clearable
          size="sm"
          onChange={e => handleSearchChange(e.target.value)}
          onClear={() => handleSearchChange('')}
        />
      </div>

      {error && (
        <div role="alert" style={{ color: 'var(--danger-500)', marginBottom: 12, fontSize: 14 }}>
          {error}
        </div>
      )}

      <div style={{ background: 'var(--bg-surface)', borderRadius: 8, border: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
        <Table<BlockedUserRow>
          columns={columns}
          data={rows}
          keyFn={row => String(row.id)}
          loading={loading}
          skeletonRows={perPage}
          stickyHeader
          emptyIcon={<Ban size={40} />}
          emptyTitle={t('blockedUsers.empty', 'Chưa có người dùng bị khóa')}
          emptyDescription={t('blockedUsers.emptyDesc', 'Thêm Telegram ID hoặc @username phía trên để khóa')}
        />
        <Pagination
          page={urlPage}
          pageSize={perPage}
          total={total}
          onPageChange={p => setParam({ page: String(p) })}
          onPageSizeChange={size => { setPerPage(size); setParam({ page: null }) }}
        />
      </div>
    </div>
  )
}
```

> **Implementer note:** verify the exact prop names against the existing shared components before finishing — `Button` (`leftIcon`, `size`, `disabled`), `useConfirm` return shape (it returns a `ConfirmFn`; confirm the argument keys `title`/`message`), and `useToast` methods (`success`/`error`). Match `BalancesPage.tsx` / another page that already uses `useConfirm` + `useToast` (e.g. `VariationsPage` or `ManualsPage`) and adjust the calls to match. Do not invent props.

- [ ] **Step 5: Wire the route in App.tsx**

In `frontend/src/App.tsx`, add the import (next to the other page imports, ~line 24):

```tsx
import { BlockedUsersPage } from './pages/BlockedUsersPage'
```

and add the route inside the protected `<Route path="/">` block (after the `balances` route, line 78):

```tsx
          <Route path="blocked-users" element={<BlockedUsersPage />} />
```

- [ ] **Step 6: Build and lint**

```bash
cd frontend
npm run lint
npm run build
```
Expected: lint passes; build completes with no TypeScript errors. Fix any prop-name mismatches surfaced by the build (per the implementer note in Step 4).

- [ ] **Step 7: Commit**

```bash
cd /home/arcrek/MTK_BOT_ORDER
git add frontend/src/pages/BlockedUsersPage.tsx frontend/src/app/routes.ts frontend/src/App.tsx frontend/src/app/layouts/Sidebar.tsx frontend/src/i18n/locales/vi/nav.json frontend/src/i18n/locales/en/nav.json
git commit -m "feat(block): add Blocked Users dashboard page"
```

---

### Task 9: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the new backend tests together**

Run:
```bash
pytest tests/test_blocked_user_model.py tests/test_block_service.py tests/test_block_commands.py tests/test_block_order_gate.py tests/test_block_topup_gate.py tests/test_block_api_gate.py tests/test_blocked_users_router.py -v
```
Expected: all PASS.

- [ ] **Step 2: Run the whole suite to confirm no regressions**

Run: `pytest -q`
Expected: no NEW failures compared to baseline. (Per project notes, ~52 pre-existing env-driven failures may already exist; confirm the count did not increase and that none of the new failures are in block-feature files.)

- [ ] **Step 3: Lint the full backend touch set**

Run: `ruff check src/ tests/`
Expected: no errors in the files this plan created/modified.

- [ ] **Step 4: Frontend build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Final commit (if anything was fixed in verification)**

```bash
git add -A
git commit -m "test(block): verify block-user feature end to end" || echo "nothing to commit"
```

---

## Self-Review Notes

- **Spec coverage:** standalone table (T1), pre-block by id/username (T1/T2 `add_block`), `is_blocked` matches either key (T2), `/block` + `/unblock` admin-gated (T3), order gate fail-fast (T4), both topup gates (T5), API gate 403 (T6), dashboard list/add/remove (T7), frontend page + nav (T8), no audit fields (T1 stores only id/username/created_at). Accepted limitation (pending-order completion) is documented in the spec, intentionally not coded.
- **Type/name consistency:** `is_blocked(telegram_user_id, username)`, `block(identifier)`, `unblock(identifier)`, `add_block(*, telegram_user_id, username)`, `remove_block(block_id)`, `list_blocked(search, page, per_page)` are used identically across T2 definition and T3–T7 call sites. Migration head `j0e1f2a3b4c5` → new revision `k1f2a3b4c5d6`.
- **Every gate passes both id + username** (T4/T5/T6) per Global Constraints.
