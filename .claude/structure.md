# Project Structure

## Directory Map

```
MTK_BOT_ORDER/
├── src/
│   ├── bot/                    Customer-facing Telegram bot
│   ├── bot_supplier/           Supplier Telegram bot (disabled in docker-compose)
│   ├── dashboard/              FastAPI admin dashboard API
│   ├── database/               SQLAlchemy models, services, migrations
│   ├── ipn/                    Payment-agnostic IPN processor
│   ├── pay2s/                  Pay2S payment gateway integration
│   ├── payos/                  PayOS payment gateway integration
│   └── i18n/                   Translations (vi/en)
├── frontend/                   React 18 + TypeScript admin SPA
├── config/                     Pay2S/PayOS credentials, IPN settings
├── scripts/                    One-off setup scripts
├── tests/                      pytest suite (48+ files)
├── data/                       Runtime data (DB file, delivery_data/, postgres_data/)
├── run_dashboard.py            Dashboard API entry point (uvicorn)
├── wsgi.py                     Pay2S IPN server entry point (gunicorn)
├── docker-compose.yml          4 services: api, bot, frontend, postgres
├── alembic.ini                 Migration config
└── requirements.txt            33 Python packages
```

## `src/bot/` — Customer Bot

| Path | Role |
|------|------|
| `main.py` | `create_bot_application()` — registers all handlers, starts polling |
| `handlers/commands.py` | `/start`, `/products`, `/orders`, `/lang`, `/setadmin`, `/help` |
| `handlers/callbacks.py` | All inline keyboard callbacks (page nav, product select, quantity, payment, language) |
| `handlers/notification_commands.py` | `/notify_all`, `/notify_user`, `/notify_active` admin commands |
| `handlers/upgrade_handler.py` | Handles UPGRADE delivery: forwards customer account-info reply to admin |
| `messages/` | Message formatters (product list, order summary, order history) |
| `states/state_manager.py` | In-memory FSM state per Telegram user_id |
| `tasks/auto_cancel_task.py` | APScheduler job — cancels unpaid orders every 5 min |
| `utils/` | Admin check, keyboard builders, language helpers, QR generation, shared bot instance |

## `src/dashboard/` — FastAPI API

| Path | Role |
|------|------|
| `main.py` | FastAPI app init, CORS, rate limiter, router registration |
| `auth.py` | JWT creation/validation, bcrypt password hashing, `get_current_admin` dependency |
| `routers/auth.py` | `/api/auth/login`, `/api/auth/me`, `/api/auth/register` |
| `routers/products.py` | CRUD for products |
| `routers/orders.py` | Order listing, status update, CSV export |
| `routers/variations.py` | Product variation CRUD |
| `routers/bonus_tiers.py` | BonusTier configuration |
| `routers/discount_tiers.py` | DiscountTier configuration |
| `routers/pre_uploaded.py` | Pre-uploaded inventory management |
| `routers/product_upload.py` | Bulk CSV upload |
| `routers/notifications.py` | Notification settings + broadcast |
| `routers/bot_ui_settings.py` | Bot UI customization |
| `routers/payos_webhook.py` | PayOS IPN webhook (`/api/payos/webhook`) |
| `routers/statistics.py` | Revenue + order analytics |
| `routers/iotd.py` | Image of the Day feature |

## `src/database/` — Data Layer

| Path | Role |
|------|------|
| `connection.py` | Singleton engine + session factory, `get_db_session` FastAPI dependency |
| `models/base.py` | SQLAlchemy `DeclarativeBase` |
| `models/enums.py` | `DeliveryType`, `OrderStatus`, `SupplierOrderStatus` |
| `models/*.py` | 18 model files (see database.md for schema) |
| `services/*.py` | 23 service classes — all business logic lives here |
| `migrations/` | Alembic migration scripts |

## `src/ipn/` — Payment Processor

| Path | Role |
|------|------|
| `processor.py` | `IPNOrderProcessor` — payment-agnostic; handles PRE_UPLOADED and UPGRADE delivery |
| `__init__.py` | Exports `set_global_bot`, `get_ipn_processor` |

## `src/pay2s/` & `src/payos/`

| Path | Role |
|------|------|
| `pay2s/payment.py` | `create_payment()` — calls Pay2S REST API |
| `pay2s/signature.py` | HMAC-SHA256 signing and IPN verification for Pay2S |
| `pay2s/ipn.py` | Flask app — receives Pay2S callback at `/api/pay2s/ipn` |
| `payos/client.py` | `PayOSClient.create_payment_link()` and cancellation |
| `payos/signature.py` | HMAC-SHA256 checksum for PayOS requests |

## `frontend/src/`

| Path | Role |
|------|------|
| `App.tsx` | Route definitions |
| `pages/` | Full page components (Products, Orders, Variations, etc.) |
| `components/` | Reusable UI widgets |
| `contexts/` | Auth context, theme context |
| `i18n/` | Frontend translations |
| `styles/` | Dark SaaS theme constants |

## Entry Points

| Command | File | What it does |
|---------|------|-------------|
| `python -m src.bot.main` | `src/bot/main.py` | Start customer Telegram bot (polling) |
| `python run_dashboard.py` | `run_dashboard.py` | Start FastAPI on port 8001 via uvicorn |
| `python run_ipn_server.py` | (not in docker; see `wsgi.py`) | Start Flask IPN server on port 5001 |
| `docker compose up` | `docker-compose.yml` | Start api + bot + frontend + postgres |

## Critical Files to Read First

1. `src/database/connection.py` — understand session lifecycle
2. `src/ipn/processor.py` — core payment + delivery logic
3. `src/bot/main.py` — handler registration order matters
4. `src/database/models/enums.py` — enum values used everywhere
5. `src/dashboard/auth.py` — JWT + RBAC dependency chain
