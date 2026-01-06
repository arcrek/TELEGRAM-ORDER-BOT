# Payment Configuration Guide

This document explains how to configure the Pay2S payment gateway for the MTK Bot Order System, both for local development and Docker deployment.

---

## Quick Start

### For Docker Deployment

1. **Update your `.env` file with Pay2S credentials:**

```bash
PAY2S_ENDPOINT=https://sandbox-payment.pay2s.vn/v1/gateway/api/create
PAY2S_PARTNER_CODE=your_partner_code
PAY2S_ACCESS_KEY=your_access_key
PAY2S_SECRET_KEY=your_secret_key
DEFAULT_BANK_ACCOUNTS=[{"account_number":"1234567890","bank_id":"ACB"}]
IPN_URL=http://your-server:5001/ipn
REDIRECT_URL=https://t.me/your_bot_username
```

2. **Start Docker services:**

```bash
docker compose up -d --build
```

3. **Test payment:**
   - Open the bot in Telegram
   - Select a product and place an order
   - Click "Proceed payment" to test the payment flow

---

## Configuration Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PAY2S_ENDPOINT` | Payment gateway API endpoint | `https://sandbox-payment.pay2s.vn/v1/gateway/api/create` |
| `PAY2S_PARTNER_CODE` | Partner code from Pay2S | `PAY2S7EPF0SB1ZP27W71` |
| `PAY2S_ACCESS_KEY` | API access key | `REDACTED_PAY2S_ACCESS_KEY` |
| `PAY2S_SECRET_KEY` | Secret key for signing (KEEP SECURE!) | `REDACTED_PAY2S_SECRET_KEY` |
| `DEFAULT_BANK_ACCOUNTS` | Available payment accounts (JSON) | `[{"account_number":"1234567890","bank_id":"ACB"}]` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `IPN_URL` | `http://localhost:5001/ipn` | Webhook URL for payment notifications |
| `REDIRECT_URL` | `https://t.me/your_bot` | Where to redirect after payment |
| `IPN_PORT` | `5001` | Port for IPN server |

---

## Local Development Setup

### Method 1: Using Environment Variables (Recommended for Docker)

The bot will automatically use environment variables if the `config` module is not available:

```bash
# Set environment variables
export PAY2S_ENDPOINT="https://sandbox-payment.pay2s.vn/v1/gateway/api/create"
export PAY2S_PARTNER_CODE="your_partner_code"
export PAY2S_ACCESS_KEY="your_access_key"
export PAY2S_SECRET_KEY="your_secret_key"
export DEFAULT_BANK_ACCOUNTS='[{"account_number":"1234567890","bank_id":"ACB"}]'

# Run bot
python -m src.bot.main
```

### Method 2: Using config/config.py (Recommended for Local Development)

Edit `config/config.py` and update the hardcoded values:

```python
PAY2S_ENDPOINT = os.getenv("PAY2S_ENDPOINT", "https://sandbox-payment.pay2s.vn/v1/gateway/api/create")
PARTNER_CODE = os.getenv("PAY2S_PARTNER_CODE", "your_partner_code")
ACCESS_KEY = os.getenv("PAY2S_ACCESS_KEY", "your_access_key")
SECRET_KEY = os.getenv("PAY2S_SECRET_KEY", "your_secret_key")
DEFAULT_BANK_ACCOUNTS = [
    {
        "account_number": "1234567890",
        "bank_id": "ACB"
    }
]
```

Then run:

```bash
python -m src.bot.main
```

---

## Docker Deployment

### Step 1: Create .env File

Create `.env` in project root (never commit this):

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# Pay2S Configuration
PAY2S_ENDPOINT=https://sandbox-payment.pay2s.vn/v1/gateway/api/create
PAY2S_PARTNER_CODE=your_partner_code
PAY2S_ACCESS_KEY=your_access_key
PAY2S_SECRET_KEY=your_secret_key
DEFAULT_BANK_ACCOUNTS=[{"account_number":"1234567890","bank_id":"ACB"}]

# IPN Configuration
IPN_URL=http://your-public-domain.com:5001/ipn
REDIRECT_URL=https://t.me/your_bot_username
IPN_PORT=5001
```

### Step 2: Build and Start

```bash
docker compose up -d --build
```

### Step 3: Verify Configuration

Check if bot has correct configuration:

```bash
# Check bot environment variables
docker compose exec bot env | grep PAY2S

# Check logs for configuration
docker compose logs bot | grep -i "payment\|config"
```

---

## Bank Accounts Configuration

The `DEFAULT_BANK_ACCOUNTS` variable must be a valid JSON array. Each account needs:

- `account_number`: Bank account number
- `bank_id`: Bank code (provided by Pay2S)

### Example - Single Bank Account

```bash
DEFAULT_BANK_ACCOUNTS=[{"account_number":"1234567890","bank_id":"ACB"}]
```

### Example - Multiple Bank Accounts

```bash
DEFAULT_BANK_ACCOUNTS=[
  {"account_number":"1234567890","bank_id":"ACB"},
  {"account_number":"0987654321","bank_id":"VIETCOMBANK"},
  {"account_number":"5555666677","bank_id":"BIDV"}
]
```

### Available Bank IDs

Contact Pay2S to get the complete list of bank IDs. Common ones include:

- `ACB` - Asia Commercial Bank
- `VIETCOMBANK` - Vietcombank
- `BIDV` - BIDV
- `TECHCOMBANK` - Techcombank
- `MB` - MB Bank
- `VPB` - VP Bank

---

## How Configuration Loading Works

The bot uses a fallback mechanism to load configuration:

```
1. Try to import from config/config.py (local development)
   ↓ (if fails)
2. Fall back to environment variables (Docker)
   ↓ (if env vars not set)
3. Use placeholder values (will show configuration error to user)
```

This allows the system to work in both local development (where `config/` is in Python path) and Docker containers (where environment variables are used).

---

## Testing Payment Configuration

### 1. Check Configuration Loads

```bash
# Local development
python -c "from config.config import PAY2S_ENDPOINT, PARTNER_CODE, ACCESS_KEY, SECRET_KEY; print(f'Endpoint: {PAY2S_ENDPOINT}')"

# Docker
docker compose exec bot python -c "import os; print(os.getenv('PAY2S_ENDPOINT'))"
```

### 2. Test Payment Gateway Connection

```bash
docker compose exec bot curl -v https://sandbox-payment.pay2s.vn/v1/gateway/api/create
```

### 3. Test Complete Payment Flow

1. Send `/start` to bot in Telegram
2. Browse products: `/products`
3. Select a product
4. Select a variation
5. Adjust quantity if needed
6. Click "💳 Proceed payment"
7. Check bot logs: `docker compose logs bot --follow`

---

## Troubleshooting

### Error: "No module named 'config'"

This happens when running in Docker without proper environment variables.

**Solution:**
Ensure these variables are in your `.env` file and passed to Docker:
- `PAY2S_ENDPOINT`
- `PAY2S_PARTNER_CODE`
- `PAY2S_ACCESS_KEY`
- `PAY2S_SECRET_KEY`
- `DEFAULT_BANK_ACCOUNTS`

### Error: "Payment configuration error"

User sees: "The Pay2S endpoint is not configured correctly."

**Check:**
```bash
docker compose exec bot env | grep PAY2S_ENDPOINT
```

Make sure `PAY2S_ENDPOINT` starts with `http://` or `https://`

### Error: "Connection error to payment gateway"

Payment gateway is unreachable.

**Possible causes:**
- Wrong endpoint URL
- Network firewall blocking
- Payment gateway is down
- Internet connection issue

**Solutions:**
```bash
# Test connectivity
docker compose exec bot ping 8.8.8.8
docker compose exec bot curl -v https://sandbox-payment.pay2s.vn/v1/gateway/api/create

# Check DNS
docker compose exec bot nslookup sandbox-payment.pay2s.vn
```

### Error: "Invalid credentials"

Payment request rejected with signature error.

**Check:**
- Partner code matches exactly
- Access key matches exactly
- Secret key is correct (used for signing)
- Keys haven't expired

### Error: "No bank accounts configured"

**Solution:**
Ensure `DEFAULT_BANK_ACCOUNTS` is set in `.env`:

```bash
DEFAULT_BANK_ACCOUNTS=[{"account_number":"1234567890","bank_id":"ACB"}]
```

---

## Production Deployment

For production, follow these guidelines:

1. **Use HTTPS URLs:**
   ```bash
   PAY2S_ENDPOINT=https://api.pay2s.vn/v1/gateway/api/create  # Real endpoint
   IPN_URL=https://your-domain.com:5001/ipn                    # Must be HTTPS
   REDIRECT_URL=https://t.me/your_bot_username
   ```

2. **Use Real Credentials:**
   - Get production credentials from Pay2S
   - Do NOT use sandbox credentials
   - Update `PAY2S_PARTNER_CODE`, `PAY2S_ACCESS_KEY`, `PAY2S_SECRET_KEY`

3. **Secure Secrets:**
   - Store `.env` in secure location (not in git)
   - Use secrets management system (e.g., Kubernetes secrets, AWS Secrets Manager)
   - Never share `PAY2S_SECRET_KEY`
   - Rotate keys periodically

4. **Configure Real Bank Accounts:**
   - Update `DEFAULT_BANK_ACCOUNTS` with production accounts
   - Verify all account numbers and bank IDs

5. **Test Before Going Live:**
   - Test payment flow end-to-end
   - Verify IPN notifications are received
   - Check database for paid orders
   - Monitor logs for errors

---

## Support

For Pay2S-specific issues, contact Pay2S support:
- Website: https://pay2s.vn
- Get credentials and technical documentation from their dashboard

For application-specific issues, check:
- `TROUBLESHOOTING_PAYMENT.md` - Detailed troubleshooting guide
- `OPERATIONS.md` - System operations guide
- Bot logs: `docker compose logs bot`

