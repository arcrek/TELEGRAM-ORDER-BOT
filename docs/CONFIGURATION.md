# Configuration

Deployment configuration lives in the root `.env`; runtime operator identity lives in PostgreSQL and is edited through **General Settings**. `.env` is never dashboard-editable and must never be committed. Keep it mode `600`, store secrets in a password manager, and use only the names listed below.

## Deployment environment

`setup.sh` creates the complete `.env`. Required means the normal setup/runtime path must have a non-empty resolved value; the two published ports have Compose defaults.

| Name | Required | Secret | Validation | Default | Change method | Restart/rebuild |
| --- | --- | --- | --- | --- | --- | --- |
| `FRONTEND_URL` | Yes for setup/operator output | No | Absolute HTTP(S) URL with hostname and optional valid port; no whitespace or userinfo | `http://localhost:8082` | Edit `.env`; keep aligned with the public frontend and `CORS_ORIGINS` | None by itself |
| `VITE_API_BASE_URL` | Yes | No | Absolute HTTP(S) URL during setup; Compose requires non-empty | `http://localhost:8001` | Edit `.env` | Rebuild `frontend`; `./manage.sh restart` does this |
| `CORS_ORIGINS` | Yes | No | API accepts a comma-separated explicit origin allow-list; `*` is rejected | Same URL entered for `FRONTEND_URL` (`http://localhost:8082` in `.env.example`) | Edit `.env`; list every browser origin explicitly | Recreate/restart `api`; use `./manage.sh restart` |
| `DASHBOARD_PORT` | No | No | Setup requires a positive integer; Docker must be able to bind it | `8001` | Edit `.env` | Recreate `api`; use `./manage.sh restart` |
| `FRONTEND_PORT` | No | No | Setup requires a positive integer; Docker must be able to bind it | `8082` | Edit `.env` | Recreate `frontend`; use `./manage.sh restart` |
| `TELEGRAM_BOT_TOKEN` | Yes | Yes | Required non-empty; setup hides input; Telegram validates it when the bot connects | None | Rotate with BotFather, then edit `.env` | Restart `api` and `bot`; use `./manage.sh restart` |
| `BOT_OWNER_TELEGRAM_ID` | Yes | No | Positive integer | None | Edit `.env`; verify the owner before replacing it | Restart `bot`; use `./manage.sh restart` |
| `DB_NAME` | Yes | No | Required non-empty by Compose | `bot_order` | Set during first setup; changing an initialized deployment requires an explicit database migration | Recreate database consumers; a restart alone does not rename existing data |
| `DB_USER` | Yes | No | Required non-empty by Compose | `bot_order` | Set during first setup; rotate the PostgreSQL role and `.env` together | Recreate `postgres`, `api`, and `bot`; a restart alone does not alter an existing role |
| `DB_PASSWORD` | Yes | Yes | Required non-empty; setup hides input | None | Rotate inside PostgreSQL, update `.env`, then restart; see [Operations](../OPERATIONS.md#credential-rotation) | Recreate `postgres`, `api`, and `bot`; changing only `.env` does not change the existing role password |
| `PAYOS_CLIENT_ID` | Yes | Yes | Required non-empty; setup hides input; PayOS validates it on API calls | None | Rotate in the PayOS merchant dashboard, then edit `.env` | Restart `api` and `bot`; use `./manage.sh restart` |
| `PAYOS_API_KEY` | Yes | Yes | Required non-empty; setup hides input; PayOS validates it on API calls | None | Rotate in the PayOS merchant dashboard, then edit `.env` | Restart `api` and `bot`; use `./manage.sh restart` |
| `PAYOS_CHECKSUM_KEY` | Yes | Yes | Required non-empty; setup hides input; webhook signatures fail if it differs from PayOS | None | Rotate in PayOS and `.env` in one maintenance window | Restart `api` and `bot`; use `./manage.sh restart` |
| `DASHBOARD_SECRET_KEY` | Yes | Yes | Required non-empty by Compose; setup generates 32 random bytes encoded as 64 hexadecimal characters | None | Replace with a strong random value in `.env` | Restart `api`; all existing dashboard tokens become invalid |

Do not add runtime App Settings, database host/port overrides, provider selectors, or supplier credentials to `.env`. Compose fixes the internal PostgreSQL host and port to `postgres:5432` and exposes only the supported four-service surface.

## App Settings

All seven fields are stored in the singleton `app_settings` row. Authenticated viewers may read them; dashboard administrators may replace them through **General Settings** (`GET/PUT /api/app-settings`). Only `system_name` is exposed publicly through `GET /api/app-settings/public`.

| Field | Validation | Model default | Change method | Restart/rebuild |
| --- | --- | --- | --- | --- |
| `system_name` | Trimmed; 1–80 characters | `Bot Order System` | General Settings | None |
| `bot_url` | Trimmed `https://t.me/` URL with a 5–32 character bot username; trailing slash removed | Empty | General Settings | None |
| `support_line_1` | Trimmed; at most 200 characters; may be empty | Empty | General Settings | None |
| `support_line_2` | Trimmed; at most 200 characters; may be empty | Empty | General Settings | None |
| `timezone` | Valid IANA timezone name | `Asia/Ho_Chi_Minh` | General Settings | None; subsequent bot-rendered times use the saved value |
| `order_prefix` | Trimmed and uppercased; 2–8 letters/digits; cannot start with reserved `TU` | `ORD` | General Settings | None; changes affect new orders only and never rename existing orders |
| `api_docs_url` | Trimmed absolute HTTPS URL without embedded credentials; at most 2048 characters; may be empty | Empty | General Settings | None |

The setup wizard supplies initial values only when the singleton settings row does not yet exist. Later reruns do not replace settings. Use the dashboard for changes so deployment secrets and runtime identity remain separate.
