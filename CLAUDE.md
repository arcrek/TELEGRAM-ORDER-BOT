# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MTK Bot Order System — a Telegram bot e-commerce platform with dual-bot architecture (customer + supplier), Pay2S/PayOS payment processing, a FastAPI admin dashboard, and a React frontend. Vietnamese is the default language.

## Commands

### Python Backend

```bash
# Install dependencies (Python 3.11+ required)
pip install -r requirements.txt

# Run services (each in its own terminal)
python -m src.bot.main          # Customer Telegram bot
python -m src.bot_supplier.main # Supplier Telegram bot
python run_dashboard.py         # FastAPI dashboard API (port 8001)
python run_ipn_server.py        # Flask IPN webhook server (port 5001)

# Database
alembic upgrade head                                # Apply migrations
alembic revision --autogenerate -m "Description"   # Create migration
alembic downgrade -1                                # Rollback one

# Utility scripts
python scripts/create_admin.py                      # Create default admin (admin/admin123)
python scripts/seed_products.py                     # Seed sample products

# Testing
pytest
pytest --cov=src --cov-report=html
pytest tests/test_specific_file.py                  # Run single test file

# Code quality
ruff check .     # Lint
ruff format .    # Format
mypy src         # Type check
```

### Frontend (React/TypeScript)

```bash
cd frontend
npm install
npm run dev      # Dev server
npm run build    # Production build
npm test         # Run tests (vitest)
npm run lint     # Lint
```

### Docker

```bash
docker compose up --build      # Build and start all services
docker compose up -d --build   # Detached mode
```

## Architecture

The system has five independent processes that communicate through the database:

```
Customer Bot  ──┐
Supplier Bot  ──┤
IPN Server    ──┼──> PostgreSQL/SQLite (via SQLAlchemy service layer)
Dashboard API ──┤
Frontend      ──┘ (calls Dashboard API over HTTP)
```

### Key Directories

- **`src/bot/`** — Customer-facing Telegram bot. All handlers are async. Uses a single-message update pattern (edit message in place rather than sending new ones). State per user managed in `src/bot/states/state_manager.py`.
- **`src/bot_supplier/`** — Supplier Telegram bot; receives order notifications when customers place supplier-product orders. Currently disabled in the dashboard API (the `suppliers` and `product_supplier_assignments` routers are commented out in `src/dashboard/main.py`).
- **`src/dashboard/routers/`** — FastAPI routers: `auth`, `products`, `orders`, `statistics`, `product_upload`, `pre_uploaded`, `variations`, `bonus_tiers`, `discount_tiers`, `notifications`, `bot_ui_settings`, `app_settings`, `payos_webhook`, `iotd`, `balances`. (`suppliers` and `product_supplier_assignments` exist on disk but are not mounted.) JWT auth via `src/dashboard/auth.py`.
- **`src/utils/datetime_format.py`** — Shared datetime utilities: `to_utc_iso` (API serialization, naive→UTC+00:00), `resolve_tz`/`now_local`/`format_local` (bot timezone display using stdlib `zoneinfo`). No new dependencies.
- **`src/database/models/`** — SQLAlchemy 2.0 declarative models (`order`, `order_item`, `product`, `product_variation`, `pre_uploaded_product`, `bot_user`, `bot_admin`, `admin`, `supplier`, `supplier_order`, `product_supplier_assignment`, `notification_settings`, `bot_ui_settings`, `iotd_settings`, `bonus_tier`, `discount_tier`, `user_preference`, `topup_order`, `balance_transaction`, `app_settings`). All business logic goes through `src/database/services/`, never raw queries in handlers. `BotUser.balance` is a `BigInteger` column; balance mutations go through `BalanceService` (atomic conditional UPDATEs, never read-then-write).
- **`src/ipn/processor.py`** — Payment-agnostic IPN processor shared by both Pay2S and PayOS. Dispatches by order ID prefix: `"TU"`-prefixed IDs route to topup balance credit; all other IDs route to product-order fulfillment. Exposes `process_balance_paid_order(order_id)` for the bot UI to trigger fulfillment after `BalanceService.pay_order_with_balance` succeeds.
- **`src/pay2s/`** — Pay2S payment integration (primary). `payment.py` creates payment links; `ipn.py` is the Flask IPN server; `signature.py` handles HMAC verification.
- **`src/payos/`** — PayOS integration (secondary/alternative payment gateway); webhook handled by the `payos_webhook` dashboard router.
- **`src/i18n/locales/`** — Translation JSON files (`vi/bot.json`, `en/bot.json`). Vietnamese is default.
- **`frontend/src/pages/`** — React 18 + TypeScript dashboard pages: `Statistics`, `Products`, `Orders`, `ProductUpload`, `Inventory` (mounted at `/pre-uploaded`, includes per-variant aging warnings and date/variation/upload filters), `InventoryUpdate`, `Variations`, `BonusSummary`, `Suppliers`, `Notifications`, `BotUiSettings`, `Iotd`, `Balances` (user balance management with add/subtract/set adjustments, transaction history, and topup-order history). Dark SaaS theme (background `#0F0F0D`, card `#181816`, accent `#6EA8FF`). No gradients or glassmorphism.

### Delivery Flow

1. Customer places order → bot presents payment-method picker (Balance vs QR)
2. **Balance path**: `BalanceService.pay_order_with_balance` atomically transitions `Order.status` PENDING→PAID and deducts `BotUser.balance` (single transaction, conditional UPDATEs guard against double-spend and double-pay) → bot calls `IPNOrderProcessor.process_balance_paid_order` to trigger fulfillment
3. **QR path**: Pay2S/PayOS creates QR payment link → sent to user via bot → customer pays → gateway calls IPN endpoint → `src/ipn/processor.py` verifies signature → atomically transitions order to PAID → triggers fulfillment
4. Fulfillment dispatch by `DeliveryType`:
   - **Pre-uploaded product**: sends stored digital content directly via bot
   - **Supplier product**: notifies supplier via supplier bot; supplier fulfills manually
5. Unpaid orders AND unpaid topups auto-cancelled after 30 minutes (APScheduler job in bot)

### Balance / Topup Flow

1. Customer taps "Số dư" → bot shows current balance with `[Nạp tiền] [Lịch sử] [Đóng]`
2. Topup creates a `TopupOrder` with `"TU"`-prefixed ID → PayOS/Pay2S generates QR
3. Customer pays → gateway IPN → processor sees `"TU"` prefix → `BalanceService.credit_topup` atomically credits balance and writes a `BalanceTransaction(kind=TOPUP)` audit row
4. Admin-channel notification (`BALANCE_TOPUP_PAID`) fires through `OrderNotificationService.send_topup_paid` — same whitelist as `ORDER_PAID`, gated by `topup_notify_on_paid` toggle in `NotificationSettings`
5. Topup bounds: min 10,000 VND, max 50,000,000 VND (constants in `topup_service.py`)
6. Admin balance adjustments (dashboard `/balances` page): add/subtract/set with required reason; recorded in `BalanceTransaction` with `admin_id` attribution

### Database

- SQLite by default (`data/database.db`), PostgreSQL in production (Docker Compose ships a `postgres` service)
- All model changes require an Alembic migration — never modify tables directly
- 19+ models including: `Order`, `OrderItem`, `Product`, `ProductVariation`, `PreUploadedProduct`, `BotUser`, `Admin`, `Supplier`, `NotificationSettings`, `BonusTier`, `DiscountTier`, `IotdSettings`, `BotUiSettings`, `TopupOrder`, `BalanceTransaction`

## Environment Variables

Requires a `.env` file in project root. Key variables:

```bash
TELEGRAM_BOT_TOKEN=          # Customer bot
SUPPLIER_TELEGRAM_BOT_TOKEN= # Supplier bot
DATABASE_URL=sqlite:///data/database.db
PAY2S_PARTNER_CODE=
PAY2S_ACCESS_KEY=
PAY2S_SECRET_KEY=
PAY2S_ENDPOINT=https://sandbox-payment.pay2s.vn/v1/gateway/api/create
IPN_URL=https://your-domain.com/ipn   # Must be publicly reachable
DASHBOARD_SECRET_KEY=                  # JWT signing key
APP_TIMEZONE=Asia/Ho_Chi_Minh          # IANA timezone for bot-displayed times (default: Asia/Ho_Chi_Minh)
                                        # Overrides initial DB seed; editable at runtime via /api/app-settings
```

> **DB timezone note:** The Postgres server/session must run in UTC so `func.now()` server defaults are UTC-consistent. Verify with `SHOW timezone;` → should return `UTC`. (Docker Compose default is correct.)
>
> **Dashboard vs bot timezone:** The dashboard renders times in the **browser's local timezone** (the API serializes to `+00:00`). The bot renders in the **app timezone** configured in `APP_TIMEZONE` / `/api/app-settings`.

## Coding Conventions

- All handlers and database service functions must be `async`
- Use type hints on all functions; use Pydantic for API request/response schemas
- Database access only through `src/database/services/` — never query models directly in handlers or routes
- Bot messages: always edit the existing message rather than sending a new one
- Translations: always use the i18n system, never hardcode Vietnamese/English strings
