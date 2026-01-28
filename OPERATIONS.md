# MTK Bot Order System - Operations Guide

This guide provides instructions for operators to run, maintain, and backup the MTK Bot Order System.

---

## Table of Contents

- [System Overview](#system-overview)
- [Starting the System](#starting-the-system)
- [Stopping the System](#stopping-the-system)
- [Language Configuration](#language-configuration)
- [Monitoring](#monitoring)
- [Database Backup & Restore](#database-backup--restore)
- [User Management](#user-management)
- [Troubleshooting](#troubleshooting)
- [Maintenance Tasks](#maintenance-tasks)
- [Security Best Practices](#security-best-practices)

---

## System Overview

### Services

The system consists of 5 Docker containers:

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8001 | FastAPI dashboard backend |
| `bot` | - | Customer Telegram bot |
| `bot_supplier` | - | Supplier Telegram bot |
| `frontend` | 8082 | Web dashboard UI (nginx) |
| `ipn-server` | 5001 | Payment IPN handler |

### Data Storage

- **Database (dev)**: PostgreSQL running in `postgres-dev` container
  - Volume: `postgres_dev_data` mounted at `/var/lib/postgresql/data`
  - Default connection: `DEV_DB_*` variables in `.env` (resolved automatically if `APP_ENV=dev`)
- **Database (prod)**: PostgreSQL running in `postgres-prod` container
  - Volume: `postgres_prod_data` mounted at `/var/lib/postgresql/data`
  - Default connection: `PROD_DB_*` variables in `.env` / production env
  - SQLite volume `database-data` is still present for legacy data but no longer used once PostgreSQL is enabled

---

## Starting the System

### Initial Setup (First Time Only)

1. **Clone the repository** (if not already done):
```bash
git clone <repository_url>
cd MTK_BOT_ORDER
```

2. **Create `.env` file** with required credentials:
```bash
nano .env
```

Add these variables:
```bash
# Telegram Bot Tokens
TELEGRAM_BOT_TOKEN=your_customer_bot_token
SUPPLIER_TELEGRAM_BOT_TOKEN=your_supplier_bot_token

# Pay2S Credentials
PAY2S_PARTNER_CODE=your_partner_code
PAY2S_ACCESS_KEY=your_access_key
PAY2S_SECRET_KEY=your_secret_key

# Payment URLs
IPN_URL=https://your-domain.com/ipn
REDIRECT_URL=https://t.me/your_bot

# Frontend API URL (update with your server IP/domain)
VITE_API_BASE_URL=http://your_server_ip:8001

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost:8082,http://your_server_ip:8082

# Optional: Enable debug mode (default: false)
DEBUG=false
```

3. **Start all services**:
```bash
docker compose up -d --build
```

4. **Wait for services to be ready** (30-60 seconds):
```bash
docker compose ps
```

All services should show `running` or `healthy`.

5. **Create admin user**:
```bash
docker compose exec api python scripts/create_admin.py \
  --username admin \
  --password YourSecurePassword123 \
  --full-name "Administrator"
```


docker compose exec api python scripts/create_admin.py --username arcrek --password REDACTED_PASSWORD --full-name "arcrek"
### Regular Startup

If the system is already configured:

```bash
docker compose up -d
```

---

## Stopping the System

### Graceful Shutdown

Stop all services without removing data:
```bash
docker compose stop
```

### Complete Shutdown

Stop and remove containers (data is preserved in volumes):
```bash
docker compose down
```

### Emergency Shutdown

Force stop all containers:
```bash
docker compose kill
```

---

## Language Configuration

### Default Language
The bot uses **Vietnamese (vi)** as the default language. All new users will see Vietnamese interface unless they change it.

### Supported Languages
| Code | Language | Flag |
|------|----------|------|
| `vi` | Tiếng Việt | 🇻🇳 |
| `en` | English | 🇬🇧 |

### User Language Commands
Users can change their language anytime using:
```
/lang    - Show language selection menu
/language - Same as /lang
```

### Translation Files Location
```
src/i18n/locales/
├── vi/
│   └── bot.json    # Vietnamese translations (default)
└── en/
    └── bot.json    # English translations
```

### Modifying Translations

1. **Edit the JSON files** directly:
```bash
# Vietnamese
nano src/i18n/locales/vi/bot.json

# English
nano src/i18n/locales/en/bot.json
```

2. **Rebuild the bot container**:
```bash
docker compose up -d --build bot
```

### Key Translation Keys
| Key | Description |
|-----|-------------|
| `commands.start.welcome` | Welcome message |
| `commands.start.description` | Bot introduction |
| `commands.help.title` | Help command header |
| `payment.qr_code` | QR code instruction |
| `delivery.ready` | Delivery confirmation |

---

## Monitoring

### Check Service Status

```bash
docker compose ps
```

Expected output:
```
NAME              STATUS
api               Up (healthy)
bot               Up
bot_supplier      Up
frontend          Up
ipn-server        Up
```

### View Logs

**All services:**
```bash
docker compose logs --tail=100 --follow
```

**Specific service:**
```bash
docker compose logs api --tail=50 --follow
docker compose logs bot --tail=50 --follow
docker compose logs frontend --tail=50 --follow
```

**Save logs to file:**
```bash
docker compose logs --tail=1000 > logs_$(date +%Y%m%d_%H%M%S).txt
```

### Check Resource Usage

```bash
docker stats
```

Shows CPU, memory, network usage for each container.

### Health Checks

**API Health:**
```bash
curl http://localhost:8001/health
```

Expected: `{"status":"healthy"}`

**Frontend:**
```bash
curl http://localhost:8082
```

Expected: HTML content

---

## Database Backup & Restore

### Automated Backup (PostgreSQL)

**Linux/Mac (SQLite legacy):**
```bash
# Make script executable (first time only)
chmod +x scripts/backup_database.sh

# Create backup with auto-generated name
./scripts/backup_database.sh

# Create backup with custom name
./scripts/backup_database.sh my_backup_20240106
```

**Windows (SQLite legacy):**
```cmd
scripts\backup_database.bat

REM Or with custom name
scripts\backup_database.bat my_backup_20240106
```

### Backup Location

Backups are stored in `./backups/` directory:
```
backups/
├── backup_20240106_143022.db
├── backup_20240107_090000.db
└── my_backup_20240106.db
```

### Manual Backup

#### PostgreSQL (preferred)

**Linux/Mac:**
```bash
mkdir -p backups
docker compose exec postgres-dev pg_dump -U "$DEV_DB_USER" "$DEV_DB_NAME" > backups/dev_$(date +%Y%m%d_%H%M%S).sql
```

**Windows (PowerShell):**
```powershell
mkdir backups
docker compose exec postgres-dev pg_dump -U "$env:DEV_DB_USER" "$env:DEV_DB_NAME" > backups/dev_manual_backup.sql
```

#### SQLite (legacy)

**Linux/Mac:**
```bash
mkdir -p backups
docker run --rm \
  -v database-data:/data \
  -v "$(pwd)/backups:/backup" \
  busybox \
  cp /data/database.db /backup/manual_$(date +%Y%m%d_%H%M%S).db
```

**Windows:**
```cmd
mkdir backups
docker run --rm -v database-data:/data -v "%CD%\backups:/backup" busybox cp /data/database.db /backup/manual_backup.db
```

### Restore Database

⚠️ **WARNING**: This will replace the current database!

**Linux/Mac:**
```bash
# Make script executable (first time only)
chmod +x scripts/restore_database.sh

# Restore from backup
./scripts/restore_database.sh backups/backup_20240106_143022.db
```

**Windows:**
```cmd
scripts\restore_database.bat backups\backup_20240106_143022.db
```

The script will:
1. Stop affected services
2. Restore the database
3. Restart services

### Backup Schedule Recommendations

| Frequency | Retention | Purpose |
|-----------|-----------|---------|
| **Hourly** | 24 hours | Recent changes |
| **Daily** | 7 days | Daily operations |
| **Weekly** | 4 weeks | Weekly snapshots |
| **Monthly** | 12 months | Long-term archive |

**Automated cron example (Linux):**
```bash
# Edit crontab
crontab -e

# Add these lines:
# Hourly backup
0 * * * * cd /path/to/MTK_BOT_ORDER && ./scripts/backup_database.sh backup_hourly_$(date +\%H) >> /var/log/mtk_backup.log 2>&1

# Daily backup at 2 AM
0 2 * * * cd /path/to/MTK_BOT_ORDER && ./scripts/backup_database.sh backup_daily_$(date +\%Y\%m\%d) >> /var/log/mtk_backup.log 2>&1
```

---

## User Management

### Create New Admin User

```bash
docker compose exec api python scripts/create_admin.py \
  --username new_user \
  --password SecurePassword123 \
  --email user@example.com \
  --full-name "Full Name" \
  --role admin
```

**Roles:**
- `admin`: Full access (create/edit/delete)
- `viewer`: Read-only access

### Create Viewer (Read-Only) User

```bash
docker compose exec api python scripts/create_admin.py \
  --username viewer \
  --password ViewerPass123 \
  --role viewer \
  --full-name "Viewer User"
```

### List All Users

```bash
docker compose exec api python -c "
from src.database.connection import get_session_factory
from src.database.models.admin import Admin
session = get_session_factory()()
admins = session.query(Admin).all()
for admin in admins:
    print(f'{admin.username:20} {admin.role.value:10} Active: {admin.is_active}')
"
```

### Reset User Password

You'll need to access the database directly or create a script. Contact system administrator.

---

## Troubleshooting

### Service Won't Start

**Check logs:**
```bash
docker compose logs <service_name> --tail=50
```

**Common issues:**
- Missing environment variables in `.env`
- Port already in use (8001, 8082, 5001)
- Insufficient disk space
- Database locked (restart all services)

**Solution:**
```bash
# Stop all services
docker compose down

# Check .env file
cat .env

# Start again
docker compose up -d
```

### Login Fails on Frontend

**Symptoms:**
- "Login failed. Please try again."
- No error in console

**Check:**
1. Is API running?
   ```bash
   curl http://localhost:8001/health
   ```

2. Check API logs during login:
   ```bash
   docker compose logs api --tail=20 --follow
   ```
   Try logging in. You should see: `POST /api/auth/login`

3. Verify CORS settings:
   ```bash
   grep CORS_ORIGINS .env
   ```

4. Does admin user exist?
   ```bash
   docker compose exec api python -c "from src.database.connection import get_session_factory; from src.database.models.admin import Admin; print(f'Admins: {get_session_factory()().query(Admin).count()}')"
   ```

**Solution:**
```bash
# Rebuild frontend with correct API URL
docker compose up -d --build frontend

# Clear browser cache (Ctrl+Shift+R)
```

### Bot Not Responding

**Check bot logs:**
```bash
docker compose logs bot --tail=50
```

**Common issues:**
- Invalid bot token
- Database not accessible
- Network issues

**Verify bot token:**
```bash
grep TELEGRAM_BOT_TOKEN .env
```

**Test bot directly:**
Send `/start` to your bot on Telegram and watch logs.

### Payment Error: "Error creating payment. Please try again later."

**Symptoms:**
- User clicks "Proceed payment" but gets error message
- Error only appears sometimes (intermittent)

**Check payment configuration:**
```bash
grep -E "PAY2S_ENDPOINT|PARTNER_CODE|ACCESS_KEY|SECRET_KEY|DEFAULT_BANK_ACCOUNTS" .env
```

**Ensure these are set correctly:**
1. `PAY2S_ENDPOINT` - Must be a valid HTTPS URL (e.g., https://pay2s.example.com/api/payment)
2. `PARTNER_CODE` - Must be provided by Pay2S
3. `ACCESS_KEY` - Must be provided by Pay2S
4. `SECRET_KEY` - Must be provided by Pay2S (kept secure!)
5. `DEFAULT_BANK_ACCOUNTS` - Must be configured with at least one bank account

**Check bot logs during payment:**
```bash
docker compose logs bot --tail=100 --follow
# Then try payment in Telegram bot
```

**Common causes:**

| Error | Cause | Solution |
|-------|-------|----------|
| Configuration error | Payment endpoint not configured | Set PAY2S_ENDPOINT in .env |
| Connection error | Can't reach payment gateway | Check internet, verify endpoint URL is reachable |
| Invalid credentials | Wrong access/secret key | Verify keys with Pay2S provider |
| No bank accounts | DEFAULT_BANK_ACCOUNTS not configured | Add bank accounts to config |
| Timeout | Payment service too slow | Check network latency, increase timeout if needed |

**Test payment gateway connectivity:**
```bash
docker compose exec bot curl -v https://<your_pay2s_endpoint>
```

**Reset and retry:**
1. Check .env configuration is correct
2. Restart bot service:
   ```bash
   docker compose restart bot
   ```
3. Try payment again in Telegram bot

### Database Errors

**Symptom:** Missing table or relation errors (e.g. `relation "orders" does not exist`)

**Solution:**
```bash
# Run migrations
docker compose exec api alembic upgrade head
```

### Rate Limiting Triggered

**Symptom:** `429 Too Many Requests` on login

**Cause:** More than 5 login attempts per minute from same IP

**Solution:** Wait 1 minute and try again

**To adjust limit:** Edit `src/dashboard/routers/auth.py`, line with `@limiter.limit("5/minute")`

---

## Maintenance Tasks

### Update System

```bash
# Backup database first!
./scripts/backup_database.sh backup_before_update

# Pull latest code
git pull

# Rebuild and restart
docker compose up -d --build

# Check all services are running
docker compose ps
```

### Clean Up Old Logs

```bash
# Remove old Docker logs
docker system prune -a

# Keep containers running
docker compose up -d
```

### View Database Statistics

```bash
docker compose exec api python -c "
from src.database.connection import get_session_factory
from src.database.models.order import Order
from src.database.models.product import Product
from src.database.models.bot_user import BotUser

session = get_session_factory()()
print(f'Orders: {session.query(Order).count()}')
print(f'Products: {session.query(Product).count()}')
print(f'Users: {session.query(BotUser).count()}')
"
```

### Disk Space Monitoring

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up unused Docker resources
docker system prune -a --volumes
```

**Warning:** `--volumes` flag removes unused volumes including backups!

---

## Security Best Practices

### 1. Regular Backups

- Daily automated backups
- Test restore procedure monthly
- Store backups off-site

### 2. Keep Secrets Secure

- Never commit `.env` to git
- Use strong, unique passwords
- Rotate credentials quarterly

### 3. Monitor Access

- Review logs regularly
- Check for failed login attempts
- Monitor API rate limits

### 4. Update Regularly

- Apply security updates promptly
- Rebuild containers monthly
- Update dependencies

### 5. Network Security

- Use firewall rules
- Restrict port access
- Use HTTPS in production
- Set CORS to specific domains

### 6. Bot Token Security

If bot token is exposed:
1. Go to @BotFather on Telegram
2. Send `/mybots`
3. Select your bot
4. API Token → Revoke current token
5. Generate new token
6. Update `.env` file
7. Restart services

---

## Quick Reference

### Common Commands

```bash
# Start everything
docker compose up -d

# Stop everything
docker compose down

# View all logs
docker compose logs --follow

# Restart single service
docker compose restart api

# Backup database
./scripts/backup_database.sh

# Create admin user
docker compose exec api python scripts/create_admin.py --username admin --password pass123

# Check service health
curl http://localhost:8001/health

# Access API documentation
# Open browser: http://localhost:8001/docs
```

### Service Ports

| Service | Port | Access |
|---------|------|--------|
| Dashboard UI | 8082 | http://localhost:8082 |
| API | 8001 | http://localhost:8001 |
| API Docs | 8001 | http://localhost:8001/docs |
| IPN Server | 5001 | http://localhost:5001 |

### Emergency Contacts

- System Administrator: [Your contact]
- Database Admin: [Your contact]
- On-call Support: [Your contact]

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2024-01-06 | Initial operations guide | System |
| | Added rate limiting (5/min) | System |
| | Disabled debug mode by default | System |

---

**Need Help?** Contact your system administrator or refer to the main README.md file.

