# Emoji Thumbnail Preview — Design Spec

**Date:** 2026-06-23
**Status:** Approved (pending written review)
**Depends on:** the custom-emoji-placeholders feature (`emoji_placeholders` table + content units, spec `2026-06-22-custom-emoji-placeholders-design.md`). Branch this work from `feat/custom-emoji-placeholders` (or from `main` once that has merged).

## Summary

Show a **still image** of each configured custom (premium) emoji in the dashboard, instead of only the plain-text `raw_text` fallback. Telegram's `getCustomEmojiStickers` returns a `Sticker` whose `thumbnail` is a static `PhotoSize` even for animated emoji; the dashboard downloads that thumbnail server-side, caches the bytes in PostgreSQL, and serves it as an image. Previews appear on the dashboard Emoji-placeholders page and in the Notifications header/footer dropdowns. Thumbnails are **still images** — animated emoji will not animate.

The dashboard process already has `TELEGRAM_BOT_TOKEN` and builds `Bot` instances (see `src/dashboard/routers/notifications.py`, `product_upload.py`), so the entire fetch-and-cache lives in the dashboard, lazily on first preview request. **No bot-process changes; `/set_emo` is untouched.** Lazy fetching covers both newly created and pre-existing placeholders with one code path.

## Decisions (locked during brainstorming)

- **Storage:** thumbnail bytes in PostgreSQL (fits the "processes communicate through the DB" architecture; no shared filesystem/volume assumption).
- **Fetch timing:** dashboard-lazy only — fetched on first preview request, then cached. No capture-time (bot-side) fetch.
- **Image endpoint auth:** public (thumbnails are non-sensitive Telegram emoji art; `<img src>` can't send the JWT), but restricted to `custom_emoji_id`s already referenced by a stored placeholder (abuse guard — the server never fetches arbitrary ids).
- **Preview scope:** Emoji-placeholders page AND the Notifications header/footer dropdown options.

## Key constraint

Fetching bytes is two hops and the `getFile` path is short-lived (~1h), so we cache the **downloaded bytes**, not the URL. The bot token must stay server-side (the public image endpoint proxies cached bytes; it never exposes the token).

## Components

### 1. Data model — `emoji_thumbnail` (global cache)

| column | type | notes |
|---|---|---|
| `custom_emoji_id` | String, PK | Telegram custom emoji id |
| `data` | LargeBinary, nullable | thumbnail bytes; `NULL` = attempted but unavailable (negative cache) |
| `mime` | String, nullable | e.g. `image/webp` |
| `fetched_at` | DateTime | server-default `now()`, updated on every fetch attempt |

Keyed by emoji id (not placeholder) so an emoji reused across placeholders is fetched/stored once. A `NULL`-`data` row is a negative cache: the endpoint re-fetches only if the `NULL` row is older than a TTL (`THUMBNAIL_NEGATIVE_TTL`, default 1 hour), bounding Telegram calls when an emoji is unavailable.

One Alembic migration creates the table; it chains after the current head (`i9d0e1f2a3b4`).

### 2. Service — `EmojiThumbnailService` (sync, dashboard)

Mirrors the existing sync service style (`__init__(self, session)`):

- `get(custom_emoji_id) -> EmojiThumbnail | None`
- `store(custom_emoji_id, data: bytes, mime: str) -> EmojiThumbnail` — upsert with `data`
- `store_failure(custom_emoji_id) -> EmojiThumbnail` — upsert a `NULL`-`data` row with fresh `fetched_at`
- `is_stale_failure(row) -> bool` — `data is None and now - fetched_at > THUMBNAIL_NEGATIVE_TTL`
- `referenced_emoji_ids() -> set[str]` — parse every `EmojiPlaceholder.content` JSON and collect all `t == "emoji"` ids (the allowlist for the public endpoint). Placeholders are few; this is a cheap full scan.

### 3. Async fetch helper

A small async function used by the endpoint (the dashboard endpoint is `async`; PTB `Bot` methods are async; the DB write uses the sync session, which is fine inside an async route):

```
async def fetch_thumbnail_bytes(bot, custom_emoji_id) -> tuple[bytes, str] | None:
    stickers = await bot.get_custom_emoji_stickers([custom_emoji_id])
    if not stickers: return None
    thumb = stickers[0].thumbnail
    if thumb is None: return None
    f = await bot.get_file(thumb.file_id)
    data = bytes(await f.download_as_bytearray())
    return data, "image/webp"   # Telegram emoji thumbnails are webp
```

The bot is built the same way the existing dashboard code does (`Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))`), reusing the existing helper if one is exposed.

### 4. API

- **`GET /api/emoji-thumbnails/{custom_emoji_id}`** — public (no auth dependency). Flow:
  1. `row = service.get(id)`. If `row` has `data` → return `Response(row.data, media_type=row.mime)`.
  2. If `id not in service.referenced_emoji_ids()` → `404` (abuse guard; no Telegram call for unknown ids).
  3. If `row` is a fresh `NULL`-failure (`not is_stale_failure`) → `404` (don't re-hammer).
  4. Else fetch via `fetch_thumbnail_bytes`. Success → `service.store(...)` → return image. Failure/None → `service.store_failure(id)` → `404`.
  - Missing token / bot unavailable → treat as failure → `404`.
  - Cache headers: a modest `Cache-Control: public, max-age=...` on successful responses so browsers don't re-request every render.
- **`GET /api/emoji-placeholders`** (existing list endpoint) — add a `units` field to `EmojiPlaceholderResponse`: the parsed ordered list, each item `{"type": "text", "value": str}` or `{"type": "emoji", "emoji_id": str, "fallback": str}`. Existing fields (`id`, `name`, `configured`, `raw_text`, `token`) unchanged. Parsed from `content` JSON (empty list when unconfigured).

### 5. Frontend

- **`EmojiPreview({ units })`** — a small shared component. Renders each unit: `text` → `<span>`; `emoji` → `<img src={`${API_BASE}/api/emoji-thumbnails/${emoji_id}`} alt={fallback} class="emoji-thumb" onError={show fallback char}>`. `API_BASE` is exported from `frontend/src/shared/lib/api.ts` (the axios `baseURL`).
- **Emoji-placeholders page** — the preview cell renders `<EmojiPreview units={item.units} />` for configured rows (replacing the `raw_text` fallback); unconfigured rows keep the "run `/set_emo`" hint.
- **Notifications page** — the header/footer `Select` options render `name` plus a compact `<EmojiPreview>` via the component's option-render override (confirm the real `Select` render-option API; fall back to `name (token)` text if it has none).

### 6. Error handling

- Fetch failure, deleted emoji, no thumbnail, or missing token → negative-cache row → `404` → `<img onError>` shows the fallback char. No crash; previews degrade to today's text behavior.
- Unknown `custom_emoji_id` (not referenced by any placeholder) → `404`, never triggers a Telegram fetch.

## Testing

- **Service:** `store`/`get` round-trip; `referenced_emoji_ids` parses ids from placeholder content (incl. mixed text+emoji, multiple placeholders, unconfigured skipped); `is_stale_failure` TTL boundary.
- **Endpoint:** unknown-id → `404` with no Telegram call; cache hit returns the stored bytes + mime; fresh negative-cache → `404` without re-fetch; the fetch path with the **Telegram fetch helper mocked** (success stores + returns bytes; failure stores `NULL` + `404`).
- **List endpoint:** response includes correctly-parsed `units`.
- **Frontend:** `EmojiPreview` renders text spans + `<img>` with correct `src`, and the `onError` fallback; build + lint + vitest.
- Tests use in-memory SQLite per the existing convention; Telegram is always mocked (never a live call in tests).

## Out of scope (v1)

- Animation (thumbnails are stills by Telegram's design).
- Capture-time (bot-side) prefetch — dashboard-lazy covers all cases.
- A manual "refresh thumbnail" action — the negative-cache TTL allows natural retry; a forced refresh can be a later addition.
- Authenticated (blob-fetch) image serving — the public + known-ids-only endpoint is sufficient for non-sensitive emoji art.
