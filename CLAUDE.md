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
- **`src/bot_supplier/`** — Supplier Telegram bot; receives order notifications when customers place supplier-product orders.
- **`src/dashboard/routers/`** — FastAPI routers (auth, products, orders, suppliers, statistics, pre-uploaded, notifications, settings). JWT auth via `src/dashboard/auth.py`.
- **`src/database/models/`** — SQLAlchemy 2.0 declarative models. All business logic goes through `src/database/services/`, never raw queries in handlers.
- **`src/ipn/processor.py`** — Payment-agnostic IPN processor shared by both Pay2S and PayOS. Handles order fulfillment and triggers delivery after payment confirmation.
- **`src/pay2s/`** — Pay2S payment integration (primary). `payment.py` creates payment links; `ipn.py` is the Flask IPN server; `signature.py` handles HMAC verification.
- **`src/payos/`** — PayOS integration (secondary/alternative payment gateway).
- **`src/i18n/locales/`** — Translation JSON files (`vi/bot.json`, `en/bot.json`). Vietnamese is default.
- **`frontend/src/`** — React 18 + TypeScript dashboard. Dark SaaS theme (background `#0F0F0D`, card `#181816`, accent `#6EA8FF`). No gradients or glassmorphism.

### Delivery Flow

1. Customer places order → Pay2S creates QR payment link → sent to user via bot
2. Customer pays → Pay2S calls IPN endpoint → `src/ipn/processor.py` verifies signature
3. Processor checks order type:
   - **Pre-uploaded product**: sends stored digital content directly via bot
   - **Supplier product**: notifies supplier via supplier bot; supplier fulfills manually
4. Unpaid orders auto-cancelled after 30 minutes (APScheduler job in bot)

### Database

- SQLite by default (`data/database.db`), PostgreSQL in production
- All model changes require an Alembic migration — never modify tables directly
- 18 models including: `Order`, `Product`, `BotUser`, `Admin`, `PreUploadedProduct`, `Supplier`, `NotificationSettings`

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
```

## Coding Conventions

- All handlers and database service functions must be `async`
- Use type hints on all functions; use Pydantic for API request/response schemas
- Database access only through `src/database/services/` — never query models directly in handlers or routes
- Bot messages: always edit the existing message rather than sending a new one
- Translations: always use the i18n system, never hardcode Vietnamese/English strings
