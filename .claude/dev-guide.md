# Developer Guide

## Prerequisites

- Python 3.11+
- Node 18+ (for frontend)
- PostgreSQL 16 (or use Docker)
- A Telegram bot token (create via @BotFather)

---

## Local Setup (without Docker)

### 1. Clone & install Python dependencies

```bash
cd MTK_BOT_ORDER
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create `.env`

```bash
cp .env.example .env
# Edit .env with your values
```

Minimum required variables:

```bash
TELEGRAM_BOT_TOKEN=<your_bot_token>

# PostgreSQL (or use SQLite for testing)
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/mtkbot
# OR individual DB vars:
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=mtkbot
# DB_USER=mtkbot
# DB_PASSWORD=secret

# JWT signing key for dashboard (any long random string)
DASHBOARD_SECRET_KEY=change_me_random_32chars

# PayOS (required for payment links)
PAYOS_CLIENT_ID=
PAYOS_API_KEY=
PAYOS_CHECKSUM_KEY=
PAYOS_RETURN_URL=https://t.me/your_bot
PAYOS_CANCEL_URL=https://t.me/your_bot

# Optional
SYSTEM_NAME=MUATAIKHOANPRO
PAYMENT_PROVIDER_DEFAULT=payos
```

### 3. Run database migrations

```bash
alembic upgrade head
```

### 4. Create default admin

```bash
python scripts/create_admin.py
# Creates: admin / admin123
```

### 5. Seed sample products (optional)

```bash
python scripts/seed_products.py
```

### 6. Start services (each in a separate terminal)

```bash
# Terminal 1 — Customer bot
python -m src.bot.main

# Terminal 2 — Dashboard API
python run_dashboard.py

# Terminal 3 — Frontend dev server
cd frontend && npm install && npm run dev
```

Access dashboard: `http://localhost:5173` (Vite) → API at `http://localhost:8001`

---

## Docker Setup

### Start everything

```bash
docker compose up --build
```

Services and ports:
| Service | Port |
|---------|------|
| FastAPI dashboard | 8001 |
| React frontend | 8082 |
| PostgreSQL | 5432 |

The `bot` service waits for the `api` healthcheck to pass before starting.

### Detached mode

```bash
docker compose up -d --build
```

### View logs

```bash
docker compose logs -f api
docker compose logs -f bot
```

### Stop

```bash
docker compose down
```

### Full reset (destroys DB data)

```bash
docker compose down -v
```

---

## Environment Variables Reference

### Required in Production

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Customer Telegram bot token |
| `DATABASE_URL` or `DB_*` | PostgreSQL connection |
| `DASHBOARD_SECRET_KEY` | JWT signing key (keep secret) |
| `PAYOS_CLIENT_ID` | PayOS client ID |
| `PAYOS_API_KEY` | PayOS API key |
| `PAYOS_CHECKSUM_KEY` | PayOS HMAC key for webhook verification |
| `PAYOS_RETURN_URL` | Redirect URL after payment |
| `PAYOS_CANCEL_URL` | Redirect URL on cancel |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `SYSTEM_NAME` | `MUATAIKHOANPRO` | Shown in delivery files and messages |
| `PAYMENT_PROVIDER_DEFAULT` | `payos` | `payos` or `pay2s` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `SUPPORT_LINE_1` | — | Support contact footer line 1 |
| `SUPPORT_LINE_2` | — | Support contact footer line 2 |
| `VITE_API_BASE_URL` | `http://localhost:8001` | Frontend API base URL (build-time) |
| `DEFAULT_BANK_ACCOUNTS` | JSON array | Bank accounts for Pay2S |

---

## Common Workflows

### Add a new product

1. `POST /api/products` with `delivery_type`
2. `POST /api/variations` for each SKU
3. If `delivery_type=pre_uploaded`: upload inventory via `POST /api/products/{id}/upload` (CSV)
4. Product is live in the bot immediately (bot queries DB on every `/products` command)

### Create a database migration

```bash
# After changing a model in src/database/models/
alembic revision --autogenerate -m "Add column X to table Y"
# Review the generated file in src/database/migrations/versions/
alembic upgrade head
```

### Run tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Single file
pytest tests/test_order_service.py

# Verbose
pytest -v
```

Tests use SQLite in-memory DB — no PostgreSQL needed.

### Lint and type-check

```bash
ruff check .     # lint
ruff format .    # auto-format
mypy src         # type check
```

### Frontend build for production

```bash
cd frontend
npm run build    # outputs to frontend/dist/
```

### Access FastAPI auto-docs

```
http://localhost:8001/docs      # Swagger UI
http://localhost:8001/redoc     # ReDoc
```

---

## Pay2S IPN Server (separate deploy)

The Pay2S IPN server (`wsgi.py`) is commented out in `docker-compose.yml`. To run it:

```bash
# Development
python run_ipn_server.py   # Flask dev server on port 5001

# Production
gunicorn wsgi:app --bind 0.0.0.0:5001
```

It needs `IPN_URL` to be a publicly reachable HTTPS URL pointing to `/api/pay2s/ipn`.

---

## Useful One-Liners

```bash
# Check DB connection
python -c "from src.database.connection import get_engine; get_engine().connect().close(); print('OK')"

# Apply migrations and seed
alembic upgrade head && python scripts/create_admin.py && python scripts/seed_products.py

# Watch bot logs in Docker
docker compose logs -f bot

# Connect to PostgreSQL in Docker
docker compose exec postgres psql -U mtkbot -d mtkbot
```
