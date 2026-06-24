# Block User Feature — Design

**Date:** 2026-06-24
**Status:** Approved (pending spec review)

## Goal

Let admins block users (by Telegram ID or username) so blocked users cannot
create orders or top up their balance. Blocking is managed from a dashboard page
(list / add / remove) and from in-chat bot commands (`/block`, `/unblock`).
All other bot functionality remains available to blocked users.

## Key Decisions

- **Standalone blocklist table** is the single source of truth — a row's
  existence *is* the block. No flag is added to `BotUser`.
  - Rationale: `BotUser.is_active` is reset to `True` on every `/start`
    (`bot_user_service.py:72`) and is used for broadcast targeting and stats;
    reusing it would let a blocked user unblock themselves with `/start`.
  - A standalone table also supports **pre-blocking**: an admin can block a
    Telegram ID or username before that user has ever interacted with the bot.
- **No reason/admin audit** — store only the identifier and a `created_at`
  timestamp (used for dashboard sorting, not who/why attribution).
- **Both `/block` and `/unblock`** bot commands, admin-gated.
- **Gated actions:** order creation (bot payment-method step), topup creation,
  and the public API v1 order endpoint. Everything else is unaffected.

## Data Model

New table `blocked_users` (new SQLAlchemy model + Alembic migration):

| column             | type                         | notes                                  |
|--------------------|------------------------------|----------------------------------------|
| `id`               | Integer, PK                  |                                        |
| `telegram_user_id` | BigInteger, nullable, indexed| set when blocking by ID                |
| `username`         | String, nullable, indexed    | set when blocking by @username; stored lowercased, no leading `@` |
| `created_at`       | DateTime, server default now | for dashboard sorting                  |

- Each row blocks by **exactly one** key: either `telegram_user_id` **or**
  `username` is set (the other is `NULL`).
- Partial unique indexes prevent duplicate blocks:
  - unique on `telegram_user_id` where `telegram_user_id IS NOT NULL`
  - unique on `username` where `username IS NOT NULL`
- A user is blocked if **either** their `telegram_user_id` matches a row
  **or** their lowercased `username` matches a row.

## Components

### 1. `BlockService` (`src/database/services/block_service.py`)

Sync service (matches existing service-layer style; see memory:
bot DB services are synchronous despite CLAUDE.md wording).

```python
def is_blocked(self, telegram_user_id: int | None, username: str | None) -> bool
def block(self, identifier: str) -> BlockedUser        # parses id vs @username
def unblock(self, identifier: str) -> bool             # returns True if a row was removed
def add_block(self, *, telegram_user_id: int | None, username: str | None) -> BlockedUser
def remove_block(self, block_id: int) -> bool
def list_blocked(self, search: str | None, page: int, per_page: int) -> tuple[list[BlockedUser], int]
```

**Identifier parsing** (shared helper): a string of all digits → `telegram_user_id`;
otherwise strip a leading `@` and lowercase → `username`. Empty/invalid → error.

`is_blocked` short-circuits: query `telegram_user_id == id OR username == lower(username)`.

### 2. Bot commands (`src/bot/handlers/commands.py`, registered in `src/bot/main.py`)

- `/block <id|@username>` and `/unblock <id|@username>`.
- Authorization: existing `is_admin(telegram_user_id)` from
  `src/bot/utils/admin_check.py`. Non-admins get a "no permission" message.
- Registered with `CommandHandler` alongside `/setadmin`, `/notify_all`.
- Responses (i18n): no-permission, usage (when arg missing), blocked, unblocked,
  already-blocked, not-blocked.

### 3. Gates

Each gate calls `BlockService.is_blocked(...)` and, when blocked, returns the
"not allowed to create an order" message **before** any order/topup row is created.

- **Order (bot):** in `handle_payment()` (`src/bot/handlers/callbacks.py`, ~line 907)
  *before* `order_service.create_order(...)`. This fires when the user reaches the
  payment-method picker — matching the requested behaviour ("return ... when
  blocked user select to payment").
- **Topup (bot):** before `topup_svc.create_topup(...)` in the balance handlers
  (`src/bot/handlers/balance.py`, ~line 512-519).
- **Public API v1:** in the `/api/v1` order-creation endpoint
  (`src/dashboard/routers/api_v1.py`). The bearer token resolves to a `BotUser`;
  if that user is blocked, return an HTTP error (e.g. 403) instead of creating an
  order. Topup is not exposed via API v1, so no API topup gate is needed.

### 4. Dashboard

- **Router** `src/dashboard/routers/blocked_users.py`, mounted at
  `/api/blocked-users` in `src/dashboard/main.py`. Follows the `balances` router
  pattern (Pydantic schemas, `get_db` dependency, `require_admin_role` for
  mutations, `require_viewer_or_admin` for listing).
  - `GET /api/blocked-users` — paginated list with optional `search`.
  - `POST /api/blocked-users` — body `{ identifier: str }`; parses id vs username.
  - `DELETE /api/blocked-users/{block_id}` — remove a block.
- **Frontend** `frontend/src/pages/BlockedUsersPage.tsx`, following the
  `BalancesPage` pattern (PageHeader, Table, Pagination, search input).
  - Add route in `frontend/src/app/routes.ts` and `frontend/src/App.tsx`.
  - Add sidebar nav entry (operations group) with an appropriate icon.
  - Add page strings to the frontend i18n locale files.
  - Add input + button to add a block; per-row remove button.

### 5. i18n (`src/i18n/locales/{vi,en}/bot.json`)

New keys (Vietnamese default):

- `commands.block.*` — no_permission, usage, blocked, unblocked,
  already_blocked, not_blocked.
- `errors.user_blocked` — "Tài khoản của bạn đã bị khóa, không thể tạo đơn hàng.
  Liên hệ admin để được hỗ trợ." (and English equivalent).

## What Is NOT Affected

`/start`, balance view, transaction history, product browsing, order
fulfillment, existing payment processing (IPN), notifications, statistics, and
all other commands remain fully available to blocked users. The block check
exists **only** at the order-creation and topup-creation entry points listed
above.

## Testing

- `BlockService`: blocking/unblocking by id and by username; `is_blocked`
  matches on either key; lowercase normalization; duplicate-block is idempotent;
  unblock of a non-existent block returns False.
- Gates: blocked user is rejected at order payment step and at topup; an order/
  topup row is **not** created; non-blocked users are unaffected.
- API v1: blocked user's token cannot create an order (403).
- Compile service queries against the PostgreSQL dialect where partial unique
  indexes / case-insensitive matching are involved (memory:
  postgres-vs-sqlite-distinct-on).

## Migration / Rollout

- Alembic migration creates `blocked_users` with the two partial unique indexes.
- No data backfill (no existing block data).
- `downgrade()` drops the table.
