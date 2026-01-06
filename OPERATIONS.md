# MTK Bot Order System - Operations Guide

This guide provides instructions for operators to run, maintain, and backup the MTK Bot Order System.

---

## Table of Contents

- [System Overview](#system-overview)
- [Starting the System](#starting-the-system)
- [Stopping the System](#stopping-the-system)
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

- **Database**: SQLite stored in Docker volume `database-data`
- **Type**: Single file database (`database.db`)
- **Shared**: All services access the same database volume

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

### Automated Backup

**Linux/Mac:**
```bash
# Make script executable (first time only)
chmod +x scripts/backup_database.sh

# Create backup with auto-generated name
./scripts/backup_database.sh

# Create backup with custom name
./scripts/backup_database.sh my_backup_20240106
```

**Windows:**
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

### Database Errors

**Symptom:** `sqlite3.OperationalError: no such table`

**Solution:**
```bash
# Run migrations
docker compose exec api alembic upgrade head
```

**Symptom:** `attempt to write a readonly database`

**Solution:** Already fixed with Docker volumes, but if it persists:
```bash
docker compose down -v
docker compose up -d
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

