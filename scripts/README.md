# Scripts

Utility scripts for database management and setup.

## bootstrap_system.py

Creates the first dashboard admin and application settings in one transaction.
Pass the JSON payload through standard input so the password is never exposed in
the command line:

```bash
python -m scripts.bootstrap_system < bootstrap.json
```

Rerunning the command preserves the existing first admin and settings.

## create_admin.py

Creates a dashboard admin. Enter the password at the hidden prompt:

```bash
python scripts/create_admin.py --username owner --full-name "System Owner"
```

For automation, pass only the password through standard input:

```bash
printf '%s\n' "$ADMIN_PASSWORD" | python scripts/create_admin.py \
  --username owner --full-name "System Owner" --password-stdin
```

## seed_products.py

Seeds the database with sample products and variations based on the requirements.

### Usage

```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run the seed script
python scripts/seed_products.py
```

### What it does

- Creates 15 sample products (matching TO-plan.md examples)
- Creates variations for each product with prices and stock
- Skips products that already exist (idempotent)
- Shows progress and summary

### Sample Products Included

- ALIGHT MOTION
- APPLE MUSIC
- CANVA LIFETIME
- CANVA PRO
- CAPCUT BASIC
- CAPCUT FAMHEAD
- CAPCUT PRO
- CAPCUT PRO PO
- CHATGPT JASPAY
- CHATGPT PRIVATE
- CHATGPT SHARING
- DUOLINGO
- GSUITEXGOPAY
- GSUITEXPSC
- GOOGLE DRIVE

Each product includes variations with realistic prices and stock levels.
