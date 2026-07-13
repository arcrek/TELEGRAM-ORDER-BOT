# Architecture

## Supported service graph

The production interface is one Docker Compose project with exactly four services:

```text
                         untrusted Internet
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
      Telegram users        Browser users         PayOS webhook
             │                    │                    │
      Telegram platform       frontend                 │
             │                    │ HTTPS API calls     │
             └────────► bot       └──────────► api ◄────┘
                          │                       │
                          └──────────┬────────────┘
                                     │ private Compose network
                                     ▼
                                  postgres
```

- `postgres` runs PostgreSQL 16, has no published host port, and is the only supported database.
- `api` runs Alembic migrations before FastAPI, exposes the dashboard API and `/api/payos/webhook`, and publishes container port `8000` through `DASHBOARD_PORT` (default `8001`).
- `bot` runs the customer Telegram bot, creates PayOS payment links, performs balance-paid fulfillment, and shares delivery inventory with `api`.
- `frontend` is a static React build served by nginx on container port `80`, published through `FRONTEND_PORT` (default `8082`). Its API base URL is a build argument.

Docker Compose is the only supported runtime. PayOS is the only supported external payment provider.

## Trust boundaries

The browser, Telegram users, PayOS callbacks, and all public network input are untrusted. TLS and DNS terminate outside this repository; the operator must place the published frontend/API ports behind valid HTTPS before production use.

The frontend contains no server-side secret. It sends dashboard bearer tokens to the API, whose authentication and role checks protect operator routes. `CORS_ORIGINS` is an explicit browser-origin allow-list and refuses wildcard configuration.

The PayOS webhook is unauthenticated HTTP at the routing layer but accepts payment facts only after HMAC verification with `PAYOS_CHECKSUM_KEY`. PostgreSQL is reachable only on the private Compose network. `.env`, PostgreSQL files, backups, and delivery inventory are trusted operator data and must not be served publicly.

## Persistence and ownership

Compose uses one host bind mount and one Docker-managed named volume:

| Host path | Container path | Services | Ownership and handling |
| --- | --- | --- | --- |
| `./data/postgres_data` | `/var/lib/postgresql/data` | `postgres` | PostgreSQL owns the live files inside the container. Do not edit or copy them while live; use `./manage.sh backup` for portable backups. |
| Compose volume `delivery_data` | `/app/delivery_data` | `api`, `bot` | Holds transient generated delivery files. Both images create the mount point with non-root application ownership, so a new volume is writable on first start. Files are sensitive and are deleted after successful delivery. |

Pre-uploaded inventory is authoritative in PostgreSQL, not in the delivery
volume. The volume exists so a generated file can survive container recreation
during an interrupted delivery; it is not a substitute for a database backup.

`api`, `bot`, and `frontend` otherwise use replaceable image/container filesystems. Database dumps are written atomically to host `backups/` and are not managed by Compose. Removing containers does not remove bind-mounted host data.

## Product order flow

### PayOS QR payment

1. The bot creates a `PENDING` order using the current runtime order prefix and reserves the required pre-uploaded inventory.
2. The bot asks PayOS for a signed payment link and stores the numeric PayOS order code on the order.
3. PayOS sends a callback to `POST /api/payos/webhook`.
4. The API validates the signature and successful PayOS result, resolves the PayOS order code, converts the amount to an integer, and hands the internal order ID to the payment processor.
5. The processor requires the callback amount to equal `Order.total_amount`, records the payment transaction, moves the order through paid processing, and dispatches fulfillment.
6. Pre-uploaded content is marked used and delivered through Telegram. A delivered order is skipped on a retry; a process-local per-order lock serializes concurrent callbacks in the supported single API process.

### Stored-balance payment

1. The bot calls `BalanceService.pay_order_with_balance` for an order owned by the current Telegram user.
2. One database transaction conditionally changes the order from `PENDING` to `PAID`, conditionally deducts only when the balance is sufficient, and appends a balance audit row. A failed deduction rolls back the order transition.
3. The bot calls `process_balance_paid_order`; this path verifies the order is already `PAID` and runs the same delivery dispatch without a PayOS webhook.

Balance mutations use conditional database updates rather than read-then-write balance changes.

## Top-up flow and the `TU` invariant

Top-up IDs are generated as `TU` plus eight lowercase hexadecimal characters. Product order prefixes are rejected when they start with `TU`, preserving an unambiguous dispatch rule:

```text
internal ID starts with TU  → balance top-up
all other internal IDs      → product order
```

The bot creates a `PENDING` top-up, requests a PayOS link, and stores its PayOS order code. After a verified successful webhook, the processor checks the callback amount against the stored top-up amount. `BalanceService.credit_topup` conditionally changes only a `PENDING` top-up to `PAID`, atomically adds the balance, and records a top-up audit row. A repeated callback returns `already_processed` and cannot credit the balance twice.

## PayOS webhook processing

`POST /api/payos/webhook` follows this order:

1. Parse `signature` and the `data` object.
2. Load `PAYOS_CHECKSUM_KEY`; without it, log and skip processing.
3. Recreate the sorted PayOS data string and compare the HMAC-SHA256 signature with `hmac.compare_digest`.
4. Require payload `success` and PayOS result code `00`.
5. Convert `orderCode`, resolve an order first and then a top-up by its stored PayOS code, and convert `amount`.
6. Select a transaction reference and run the synchronous processor in an executor while retaining the FastAPI event loop for Telegram calls.
7. Require the exact stored amount before any product delivery or top-up credit.
8. Apply retry guards: delivered product orders are skipped, top-up status transition is conditional, and balance credits are atomic.

For parsed but missing, malformed, non-successful, unknown, or invalidly signed notifications, the route logs the reason and returns a success-shaped HTTP 2xx response to avoid a retry storm. Operators therefore must monitor API logs; PayOS seeing 2xx does not prove fulfillment succeeded.

## Database access rule

Business rules and mutations belong in `src/database/services/`. Bot handlers and dashboard routes must not add direct model mutations or parallel business logic. The current PayOS webhook contains a narrow read-only lookup that maps a PayOS order code to an internal order/top-up ID; all amount checks, status transitions, balance changes, audit rows, and delivery work then run through the shared processor and service layer. New database access should move toward the service boundary rather than expand this exception.

Every schema change requires an Alembic migration. The API entrypoint is the single migration runner; bot and frontend startup never run migrations.

## Runtime settings and deployment secrets

The seven App Settings fields are non-secret operator identity stored in PostgreSQL and edited at runtime through General Settings. They include the system name, bot URL, two support lines, IANA timezone, order prefix, and API documentation URL. They do not require image rebuilds.

Deployment connectivity and credentials live only in `.env`: public URLs/ports, Telegram token and owner ID, PostgreSQL name/user/password, PayOS credentials, CORS origins, and dashboard signing key. They are not dashboard-editable. `VITE_API_BASE_URL` requires a frontend rebuild; service credentials require container restart. See [Configuration](CONFIGURATION.md).

## Experimental supplier boundary

Supplier models, services, routers, and bot source remain in the tree as experimental code. The supported Compose file has no supplier service, `setup.sh` collects no supplier credential, the API does not mount supplier routers, and health/management commands know only `postgres`, `api`, `bot`, and `frontend`. Supplier-based delivery is disabled in the shared processor.

Do not enable this code by adding an ad hoc service or environment variable. It needs a dedicated threat review, data migration review, end-to-end tests, operator documentation, and an explicit opt-in Compose profile before it can become supported.
