# Custom Emoji Placeholders — Design Spec

**Date:** 2026-06-22
**Status:** Approved (pending written review)

## Summary

Let admins use Telegram **premium / custom emoji** throughout the bot (product list & detail, admin notifications, customer order messages) via reusable, named **placeholders** referenced with a `{emo:<id>}` token.

This is possible because the bot owner has **Telegram Premium**: a Premium account is allowed to *send* custom emoji in messages the bot delivers. Non-Premium customers can still *see* them rendered. There is no public API to look up a `custom_emoji_id`; the only practical way to obtain one is to read it off an incoming message that contains the emoji — which is exactly what the `/set_emo` capture flow does.

### Authoring flow (end to end)

1. **Dashboard:** admin creates a placeholder (name/label only) → system returns a numeric `id`.
2. **Bot:** admin runs `/set_emo <id>`, then sends a message containing one or more premium emoji (optionally mixed with text). The bot extracts each `custom_emoji_id` (in order, with its fallback char) and saves it to the placeholder.
3. **Authoring:** admin embeds `{emo:<id>}` tokens in any supported text field (product name/description, variation name, notification body).
4. **Rendering:** when the bot sends a message, tokens expand to `<tg-emoji>` HTML and the message is sent with `parse_mode=HTML`.
5. **Notifications page:** header + footer fields, each a searchable dropdown of configured placeholders, are prepended/appended to outgoing notifications.

## Decisions (locked during brainstorming)

- **Config model:** fully dashboard-editable (DB-backed) — admins manage placeholders without a redeploy.
- **Surfaces:** product list/details, admin notifications, customer order messages, and (opt-in, available via the same helper) general bot UI.
- **Mechanism:** token-based (`{emo:<id>}`) authored in text fields, expanded at send time. No auto-swapping of bare unicode emoji in v1.
- **Capture flow:** two-step — `/set_emo <id>` then a follow-up message with the emoji(s), using the existing state manager.
- **Render wiring:** one central, opt-in helper applied at chosen formatters/send paths. A message only switches to `parse_mode=HTML` when it actually contains a `{emo:}` token (or has a header/footer set), so existing plain-text messages are byte-for-byte unchanged.

## Key technical constraint

Custom emoji render **only** via `parse_mode=HTML` (`<tg-emoji emoji-id="…">fallback</tg-emoji>`) or explicit message entities. We use HTML. The central correctness requirement: any dynamic/human content (product names, descriptions, usernames) must be **HTML-escaped before** tokens are substituted, so a stray `<`, `>` or `&` never breaks rendering. The render order (escape → substitute) guarantees this; `{emo:N}` tokens contain no HTML-special characters, so they survive the escape step and are then replaced with already-safe HTML.

## Components

### 1. Data model

New table **`emoji_placeholders`**:

| column | type | notes |
|---|---|---|
| `id` | Integer PK (autoincrement) | the `{emo:id}` number |
| `name` | String, not null | admin-facing label; searchable in dropdowns |
| `content` | JSON / Text, nullable | ordered units (see below). Null until `/set_emo` configures it |
| `raw_text` | Text, nullable | original captured message text, for dashboard preview |
| `set_by` | BigInteger, nullable | telegram id of the admin who configured it |
| `created_at` | DateTime | server-default UTC |
| `updated_at` | DateTime | server-default UTC, on-update |

`content` unit shape (ordered list):

```json
[
  {"t": "emoji", "id": "5368324170671202286", "fb": "🔔"},
  {"t": "text",  "v": "THÔNG BÁO"}
]
```

- `t: "emoji"` → a custom emoji: `id` = `custom_emoji_id`, `fb` = the fallback unicode char the admin typed.
- `t: "text"` → literal text between/around emoji.

**`notification_settings`** gains two nullable columns:

- `header_placeholder_id` Integer, nullable — soft FK to `emoji_placeholders.id`
- `footer_placeholder_id` Integer, nullable — soft FK to `emoji_placeholders.id`

Soft FK (no DB-level constraint) so deleting a placeholder can't fail a notification write; a dangling reference simply resolves to empty at render time.

### 2. Service — `EmojiPlaceholderService` (sync)

Mirrors the existing sync service layer (`src/database/services/`). Methods:

- `create(name) -> int` — returns the new id
- `list() -> list[EmojiPlaceholder]`
- `get(id) -> EmojiPlaceholder | None`
- `rename(id, name) -> EmojiPlaceholder`
- `delete(id) -> bool`
- `set_content(id, units, raw_text, set_by) -> EmojiPlaceholder` — called by the bot capture flow

Includes a small in-process cache (`id -> rendered HTML`) invalidated on every write (`set_content`, `rename`, `delete`), since rendering runs on every product/notification send.

### 3. Render helper — `EmojiRenderer`

`render(text: str) -> tuple[str, str | None]`:

```text
if "{emo:" not in text:
    return (text, None)                  # untouched; sent as plain text exactly as today
escaped = html.escape(text)              # escape all human content first
result  = TOKEN_RE.sub(resolve, escaped) # replace {emo:N} with placeholder HTML (already safe)
return (result, "HTML")
```

- `TOKEN_RE` matches `{emo:<digits>}`.
- `resolve(N)`:
  - configured placeholder → concatenation of units: emoji → `<tg-emoji emoji-id="<id>"><fb></tg-emoji>`, text → `html.escape(v)`.
  - missing or empty (created but not yet `/set_emo`-configured) placeholder → empty string (token silently dropped — never a broken message).
- Lives in bot utils; uses `EmojiPlaceholderService` (with cache) to resolve ids.

### 4. Capture flow (`/set_emo`)

- **Command:** `CommandHandler("set_emo", ...)`, gated by `is_admin(user.id)` (`src/bot/utils/admin_check.py`). Parses the id argument, verifies the placeholder exists, sets state `awaiting_emoji_input=True`, `pending_emoji_placeholder_id=<id>`, replies asking for the emoji(s).
- **Follow-up:** a `MessageHandler` in its **own handler group**, effective only when `awaiting_emoji_input` is set (otherwise returns immediately so it doesn't shadow other text handlers). It:
  1. Uses PTB `message.parse_entities([MessageEntityType.CUSTOM_EMOJI])` (PTB does the UTF-16 offset math) plus the message text to build the ordered `content` units.
  2. Calls `service.set_content(...)`, stores `raw_text`, confirms with a short summary (e.g. "Captured 3 custom emoji for placeholder 5").
  3. Clears the state.
- Re-running `/set_emo N` overwrites — this is the edit path.
- **New `UserState` fields:** `awaiting_emoji_input: bool = False`, `pending_emoji_placeholder_id: int | None = None`.
- **Registration:** add the `CommandHandler` and the gated `MessageHandler` (next free group) in `src/bot/main.py`.

### 5. Integration points (opt-in)

- **Product list / detail** (`src/bot/messages/product_formatter.py`, `product_detail_formatter.py`): pass `name` / `description` / variation text through `EmojiRenderer.render(...)`; send with the returned `parse_mode`.
- **Admin notifications** (`src/database/services/order_notification_service.py`):
  - `_format_message` builds the body. When a header/footer placeholder is set **or** the body contains a token, HTML-escape the dynamic fields, prepend the rendered header and append the rendered footer.
  - `send_message_to_whitelist_async` passes `parse_mode="HTML"` in that case; otherwise sends plain text unchanged.
- **Customer order messages** (payment prompt / order-done / balance & topup flows): route their text through the same helper at the send point.

### 6. Dashboard

- **New "Emoji" page** (router mirrors `src/dashboard/routers/app_settings.py`; page mirrors an existing CRUD page):
  - Lists placeholders with `id`, `name`, a **configured ✓ / empty** badge, and `raw_text` as a plain-text preview. (Telegram custom emoji can't animate in a browser; the plain-text fallback is the honest preview.)
  - Actions: **create** (name only → returns id, shown with the hint "run `/set_emo <id>` in the bot and send your emoji"), **rename**, **delete**.
- **API** (admin-gated, mirrors existing routers, mounted in `src/dashboard/main.py`):
  - `GET /api/emoji-placeholders` — list
  - `POST /api/emoji-placeholders` — `{name}` → `{id, ...}`
  - `PATCH /api/emoji-placeholders/{id}` — `{name}`
  - `DELETE /api/emoji-placeholders/{id}`
  - The bot writes `content` directly through the service, not via this API.
- **Notifications page:** two searchable dropdowns (header / footer) populated from the placeholder list, persisting `header_placeholder_id` / `footer_placeholder_id` to `notification_settings`.

### 7. Migration

A single Alembic migration (in `src/database/migrations/versions/`) that:

- creates `emoji_placeholders`
- adds `header_placeholder_id`, `footer_placeholder_id` to `notification_settings`

Includes a matching `downgrade()`.

## Testing

- **Capture parsing:** entities + text → ordered units, for emoji-only and mixed text+emoji messages.
- **Renderer:** token substitution; HTML-escaping of surrounding content; missing/empty placeholder → dropped; no-token input → returned unchanged with `parse_mode=None`.
- **Notification assembly:** header/footer prepend/append plus correct escaping of dynamic fields.
- Tests use in-memory SQLite per the existing suite convention.

## Edge cases & risks

- **Escaping correctness** — the primary risk; mitigated by the fixed render order (escape → substitute) and dedicated tests.
- **Token referencing a deleted/empty placeholder** — resolves to empty; never a broken message.
- **Non-admin `/set_emo`** — rejected by `is_admin`.
- **Cache staleness** — cache invalidated on every service write.

## Out of scope (v1)

- Auto-swapping bare unicode emoji to custom emoji (tokens only).
- Injecting tokens into i18n menu strings / rewriting general handlers (the helper is available if desired later, but not part of this work).
- Inline (`/set_emo 5 🔔`) or reply-to capture variants (two-step only).
