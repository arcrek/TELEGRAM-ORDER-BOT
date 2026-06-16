# Timezone Support — Design & Implementation Spec

Date: 2026-06-16
Status: Approved, ready for implementation

## Goal

Add timezone handling to the MTK Bot Order System:

- **Customer bot:** display all user-facing times in a **single, globally-configured app timezone** (IANA, default `Asia/Ho_Chi_Minh` / UTC+7).
- **Dashboard/frontend:** display times in the **browser's local timezone** (auto-detected), and fix the existing latent off-by-offset parsing bug.
- **Config:** the global app timezone is editable from the dashboard (admin only) and seeded from an env var default.

Storage stays naive-UTC in the DB (Postgres-only project; `DateTime`/`timestamp without time zone` columns unchanged). The work is about *interpreting and presenting* the stored UTC values correctly, plus one configurable setting.

## Background / current state (verified)

- DB writes use `datetime.now(timezone.utc)` and store **naive** values. `server_default=func.now()` columns rely on the DB session being UTC.
- Bot has a single hardcoded `tz_offset = 7 * 3600` in `src/bot/handlers/commands.py:752` (`/doanhthu`), and literal `"... UTC"` strftime timestamps in:
  - `src/database/services/order_notification_service.py:198` and `:364`
  - `src/bot/handlers/upgrade_handler.py:478`
- API routers serialize datetimes with bare `.isoformat()` (44 sites across 11 router files). On a naive datetime this emits `2026-06-16T10:30:00` with **no zone designator**.
- Frontend `frontend/src/shared/lib/format.ts` formats with `Intl.DateTimeFormat` and **no explicit `timeZone`** (= browser-local). Because the API string has no zone, `new Date(str)` parses it as **browser-local**, shifting UTC values by the browser offset. **This is the latent bug.**
- Existing patterns to mirror:
  - Singleton settings: `src/database/models/bot_ui_settings.py` + `src/database/services/bot_ui_settings_service.py` (singleton id `"global"`) + `src/dashboard/routers/bot_ui_settings.py` (GET/PUT, `require_admin_role` to edit, `require_viewer_or_admin` to read).
  - Frontend settings page: `frontend/src/pages/BotUiSettingsPage.tsx`, routed in `frontend/src/App.tsx`.
- Alembic migrations live in `src/database/migrations/versions/` (config `alembic.ini` → `script_location = src/database/migrations`).
- Bot DB sessions are passed into handlers; `BotUiSettingsService(session)` is the access pattern (see `commands.py:30-34`).

## Design

### 1. Foundation — make UTC explicit end-to-end (correctness fix)

**1a. API serialization helper.** Add `to_utc_iso(dt: datetime | None) -> str | None` in a shared util module `src/dashboard/serialization.py` (or `src/utils/datetime_format.py` — see §2). Behavior:
- `None` → `None`.
- naive datetime → assume UTC, attach `tzinfo=timezone.utc`, return `.isoformat()` (yields `+00:00`).
- aware datetime → convert to UTC, return `.isoformat()`.

Replace the 44 bare `.isoformat()` datetime emissions across these routers with `to_utc_iso(...)`:
`orders.py, pre_uploaded.py, products.py, variations.py, bonus_tiers.py, discount_tiers.py, notifications.py, suppliers.py, product_supplier_assignments.py, api_v1.py, auth.py`.
(Only datetime fields — leave any non-datetime `.isoformat()` if present. Verify each site is a datetime.)

**1b. DB invariant.** Document (in code comment near the engine setup and/or `.env.example`) that the Postgres server/session must run in UTC so `func.now()` defaults are UTC-consistent. No schema change. Add a one-time verification note in the spec's testing section.

### 2. Bot — single global app timezone

**2a. New singleton model `AppSettings`** — `src/database/models/app_settings.py`:
- Table `app_settings`, singleton id `"global"` (mirror `BotUiSettings`).
- Column `timezone: String`, not null, default `"Asia/Ho_Chi_Minh"`.
- `created_at` / `updated_at` like the other settings models.
- Register the model wherever models are imported for metadata (mirror `bot_ui_settings`).

**2b. Service `AppSettingsService`** — `src/database/services/app_settings_service.py`, mirror `BotUiSettingsService`:
- `get_settings()` creates the singleton on first read. **Default timezone seeded from env `APP_TIMEZONE`** (fallback `Asia/Ho_Chi_Minh`) at creation time.
- `update_settings(timezone=...)` validates the IANA name against `zoneinfo.available_timezones()`; raise `ValueError` on invalid (router maps to HTTP 400).

**2c. Datetime helper module** — `src/utils/datetime_format.py` (create `src/utils/__init__.py` if needed):
- `resolve_tz(name: str) -> ZoneInfo` — invalid name → log warning + fall back to `Asia/Ho_Chi_Minh`.
- `now_local(tz: ZoneInfo) -> datetime` — current time in tz.
- `format_local(dt: datetime, tz: ZoneInfo, fmt: str = "%Y-%m-%d %H:%M") -> str` — treat naive `dt` as UTC, convert to tz, format. Include a zone label (e.g. append `%Z` or the offset) so users see which zone.
- Uses stdlib `zoneinfo` only — **no new dependency**.
- Optionally place `to_utc_iso` here too and have the dashboard import it (keeps one datetime util home). Implementer's choice; keep it in one place.

**2d. Replace ad-hoc bot handling** (all read the app timezone via `AppSettingsService` with the handler's session, then use the helper):
- `commands.py:750-753` (`/doanhthu`): replace hardcoded `tz_offset` with `now_local(resolve_tz(settings.timezone))`. The date-window math must use the same tz consistently.
- `order_notification_service.py:198` & `:364`: replace literal-UTC strftime with `format_local(...)` in app tz.
- `upgrade_handler.py:478`: same.
- Keep all i18n through the existing system; don't hardcode strings. If a zone label is shown, it's a formatted value, not a translated string.

### 3. Dashboard — config UI + corrected browser-local display

**3a. Backend router `app_settings`** — `src/dashboard/routers/app_settings.py`, mirror `bot_ui_settings.py`:
- `GET` (require_viewer_or_admin) → `{ timezone: str }`.
- `PUT` (require_admin_role) → validates via service, returns updated `{ timezone }`. Invalid tz → 400 with clear message.
- Register in `src/dashboard/main.py` (import in the router import block + `app.include_router(app_settings.router, prefix="/api/app-settings", tags=["app-settings"])`).

**3b. Frontend display fix** — `frontend/src/shared/lib/format.ts`:
- Add an internal `parseUtc(value)` helper: if `value` is a string lacking a zone designator (no `Z`/`+hh:mm`), append `Z` before `new Date()`; otherwise pass through. (After §1a the API sends `+00:00`, so this is also a safety net.)
- Route `formatDate`, `formatDateTime`, `formatRelative` through `parseUtc`. Keep rendering browser-local (no explicit `timeZone`) per decision.
- Add a unit test (vitest) proving a naive-UTC input renders correctly shifted under a mocked browser zone.

**3c. Frontend config page** — new **General Settings** page:
- `frontend/src/pages/GeneralSettingsPage.tsx` (+ matching CSS), mirror `BotUiSettingsPage.tsx` structure/theme.
- IANA timezone dropdown (use `Intl.supportedValuesOf('timeZone')` for the option list; fall back to a curated short list if unsupported). Loads/saves via `/api/app-settings`.
- **UI copy must clarify:** this timezone controls **the bot's** displayed times; the dashboard always shows **your browser's** local time.
- Route it in `frontend/src/App.tsx` and add to the nav/sidebar wherever `BotUiSettings` appears.

### 4. Testing

- **Python unit tests** (`tests/`):
  - `format_local` / `now_local` at fixed instants for a fixed-offset zone and a DST zone.
  - `to_utc_iso`: `None`, naive→`+00:00`, aware→UTC.
  - `AppSettingsService`: default seed from env, invalid tz rejected, valid tz persisted.
- **Frontend test** (vitest): `format.ts` naive-UTC parse correctness under mocked `Intl` resolved zone.
- **Manual verification note:** confirm Postgres session TZ is UTC (`SHOW timezone;` → `UTC`).

### 5. Migration / rollout

- One Alembic migration creating `app_settings` (autogenerate then review). Seed of the singleton row happens lazily via `get_settings()`; no data migration needed.
- New env var `APP_TIMEZONE` documented in `.env.example` / CLAUDE.md env section (default `Asia/Ho_Chi_Minh`).

## Out of scope (YAGNI)

- Per-user timezone selection in the bot.
- Per-admin server-side timezone preference (dashboard uses browser-local).
- Changing DB columns to `timestamptz`.
- Unrelated refactors of the touched routers.

## Sub-decisions (locked)

1. Timezone config lives on a **new General Settings page**, not bolted onto Bot UI Settings.
2. API serialization fix applied across **all** datetime-emitting routers, not just orders.
