# Scripts

Utility scripts for database management and setup.

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

