# MTK Bot Order System

A comprehensive Telegram bot order system that allows users to browse products, place orders, and receive deliveries through an interactive single-message interface. The system integrates with Pay2S payment service and supports two delivery types: pre-uploaded products (instant delivery) and supplier-based products (manual delivery).

## Project Structure

```
MTK_BOT_ORDER/
├── src/
│   ├── bot/                    # Customer Telegram bot
│   │   ├── handlers/            # Command and callback handlers
│   │   ├── messages/            # Message formatters
│   │   └── states/              # State management
│   ├── bot_supplier/            # Supplier Telegram bot
│   │   └── handlers/            # Supplier bot handlers
│   ├── dashboard/               # Admin dashboard API (FastAPI)
│   │   ├── routers/             # API routes (auth, products, orders, statistics, suppliers)
│   │   └── auth.py              # Authentication & authorization
│   ├── database/                # Database layer
│   │   ├── models/              # SQLAlchemy models
│   │   ├── services/            # Business logic services
│   │   └── migrations/          # Alembic migrations
│   └── pay2s/                   # Pay2S payment integration
│       ├── payment.py           # Payment creation
│       ├── ipn.py               # IPN server
│       └── ipn_order_processor.py  # Order processing after payment
├── frontend/                    # React + TypeScript dashboard UI
│   └── src/
│       ├── components/          # Reusable UI components
│       ├── layouts/             # Dashboard layout
│       ├── pages/                # Dashboard pages
│       ├── contexts/            # React contexts (Auth, Theme)
│       └── styles/              # Theme system
├── config/                      # Configuration
├── scripts/                      # Utility scripts
│   ├── create_admin.py          # Create admin user
│   └── seed_products.py        # Seed sample products
├── tests/                       # Test suite
├── run_dashboard.py            # Dashboard API runner
├── run_ipn_server.py           # IPN server runner
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # Docker Compose configuration
└── README.md                   # This file
```
## Installation

### Prerequisites

1. **Python 3.11+** installed
2. **Node.js 18+** and npm (for frontend)
3. **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
4. **Pay2S credentials** (configured in `config/config.py`)

### Step 1: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 3: Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Telegram Bots
TELEGRAM_BOT_TOKEN=your_customer_bot_token_here
SUPPLIER_TELEGRAM_BOT_TOKEN=your_supplier_bot_token_here

# Database (optional - defaults to sqlite:///data/database.db)
DATABASE_URL=sqlite:///data/database.db

# Pay2S (REQUIRED for payment functionality)
PAY2S_ENDPOINT=https://sandbox-payment.pay2s.vn/v1/gateway/api/create
PAY2S_PARTNER_CODE=your_partner_code
PAY2S_ACCESS_KEY=your_access_key
PAY2S_SECRET_KEY=your_secret_key
DEFAULT_BANK_ACCOUNTS=[{"account_number":"1234567890","bank_id":"ACB"}]

# IPN Server (optional - defaults in config.py)
IPN_HOST=0.0.0.0
IPN_PORT=5001
IPN_URL=https://your-public-domain.com/ipn

# Payment Redirect (optional)
REDIRECT_URL=https://t.me/your_bot_username

# Dashboard (optional)
DASHBOARD_PORT=8001
DASHBOARD_SECRET_KEY=your_secret_key_for_jwt
```

### Step 4: Initialize Database

```bash
# Create database tables
alembic upgrade head

# If migration doesn't exist, create it:
alembic revision --autogenerate -m "Initial migration: create all tables"
alembic upgrade head
```

### Step 5: Create Admin User

```bash
# Create default admin (username: admin, password: admin123)
python scripts/create_admin.py

# Or create custom admin
python scripts/create_admin.py --username myadmin --password mypassword123 --email admin@example.com --full-name "My Name"
```

**⚠️ Important:** Change the default password after first login!

### Step 6: Seed Sample Products (Optional)

```bash
# Add sample products for testing
python scripts/seed_products.py
```

## Running the System

### Option A: Run All Services Separately

#### Terminal 1: Customer Telegram Bot
```bash
python -m src.bot.main
```

#### Terminal 2: Supplier Telegram Bot
```bash
python -m src.bot_supplier.main
```

#### Terminal 3: IPN Server
```bash
python run_ipn_server.py
```

#### Terminal 4: Dashboard API
```bash
python run_dashboard.py
```

#### Terminal 5: Frontend Dashboard
```bash
cd frontend
npm run dev
```

### Option B: Use Docker Compose

All services are containerized with multistage Dockerfiles:
- `api` (FastAPI dashboard)
- `bot` (customer Telegram bot)
- `bot_supplier` (supplier Telegram bot)
- `frontend` (React + nginx)
- `ipn-server` (Flask + Gunicorn)

```bash
# Build and start everything
docker compose up --build

# Run detached
docker compose up -d --build
```

## Access Points

- **Customer Bot:** Search for your bot on Telegram
- **Supplier Bot:** Search for your supplier bot on Telegram
- **Dashboard API:** `http://localhost:8001`
- **Dashboard API Docs:** `http://localhost:8001/docs`
- **Frontend Dashboard:** `http://localhost:8082`
- **IPN Endpoint:** `http://localhost:5001/ipn`

## Technology Stack

### Backend
- **Python 3.11+**
- **FastAPI** - Dashboard API framework
- **Flask** - IPN server
- **python-telegram-bot** (v20+) - Telegram bot framework
- **SQLAlchemy 2.0** - ORM
- **Alembic** - Database migrations
- **Pydantic** - Data validation

### Frontend
- **React 18** with TypeScript
- **Vite** - Build tool
- **React Router** - Routing
- **Axios** - HTTP client
- **Lucide React** - Icons
- **Chart.js** - Data visualization (for future statistics)

### Database
- **SQLite** (development)
- Supports PostgreSQL (production)

### Design System
- **Premium Dark SaaS Theme**
  - Background: `#0F0F0D`
  - Card BG: `#181816`
  - Border: `#2A2A26`
  - Accent Blue: `#6EA8FF`
  - No gradients, no glassmorphism, minimalist design

## Operations & Maintenance

For detailed operator instructions including:
- Starting/stopping the system
- Database backup and restore
- Monitoring and troubleshooting
- User management

**See: [OPERATIONS.md](OPERATIONS.md)**

### Quick Backup

**Linux/Mac:**
```bash
./scripts/backup_database.sh
```

**Windows:**
```cmd
scripts\backup_database.bat
```

## Testing

```bash
# Run all Python tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run frontend tests
cd frontend
npm test
```

## Development

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Code Quality

```bash
# Lint Python code
ruff check .

# Format Python code
ruff format .

# Type check Python code
mypy src

# Lint frontend code
cd frontend
npm run lint
```

## Documentation

- **Operations Guide:** `OPERATIONS.md` - Complete guide for operators (running, monitoring, backup)
- **Implementation Plan:** `.claude/plans/telegram-bot-order-system.md`
- **Frontend README:** `frontend/README.md`

## License

MIT
