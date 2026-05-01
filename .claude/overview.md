# System Overview

## Purpose

MTK Bot Order is a Telegram-based e-commerce platform for selling digital products (account credentials, codes, upgrades). Customers browse and purchase through a Telegram bot; delivery is automatic (pre-uploaded files) or semi-manual (UPGRADE flow). Business owners manage everything through a React admin dashboard.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Customer bot | python-telegram-bot 22.7+, Python 3.11+ |
| Dashboard API | FastAPI 0.136+, Uvicorn |
| IPN server (Pay2S) | Flask 3.1+, Gunicorn |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Database | PostgreSQL 16 (SQLite for tests) |
| Background jobs | APScheduler |
| Auth | JWT (HS256), bcrypt |
| Rate limiting | slowapi |
| Frontend | React 18.3, TypeScript 5.9, Vite |
| Payments | PayOS (primary), Pay2S (secondary) |
| Delivery files | Local filesystem (`delivery_data/`) |

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│  Telegram Clients                                        │
│   └─ Customer chats ──────► Customer Bot (port 8001)    │
└──────────────────────────────────────────────────────────┘
                                        │ polling
                                        ▼
                           ┌─────────────────────┐
                           │  src/bot/main.py     │
                           │  python-telegram-bot │
                           └────────┬────────────┘
                                    │ SQLAlchemy session
                                    ▼
                         ┌──────────────────────┐
                         │   PostgreSQL 16       │◄──── Alembic migrations
                         └──────────────────────┘
                                    ▲
              ┌─────────────────────┼────────────────────────┐
              │                     │                        │
  ┌───────────┴──────┐   ┌──────────┴──────────┐  ┌────────┴──────────┐
  │  FastAPI Dashboard│   │  Flask IPN (Pay2S)  │  │  React Frontend  │
  │  run_dashboard.py │   │  wsgi.py / port 5001│  │  frontend/        │
  │  port 8001        │   └─────────────────────┘  │  port 8082 (prod) │
  └───────────────────┘                             └───────────────────┘
           ▲
           │ PayOS webhook POST /api/payos/webhook
  PayOS ───┘
  Pay2S ──────────────────────────────────────────► IPN server /api/pay2s/ipn
```

## End-to-End Request Flow

### Customer Purchase

```
1. Customer sends /start or /products to bot
2. Bot queries ProductService → lists active products with variations
3. Customer selects product + variation + quantity
4. BonusTier/DiscountTier computed → order preview shown
5. Customer confirms → Order created (status=PENDING)
6. Bot calls PayOSClient.create_payment_link() or Pay2S create_payment()
7. QR code + payment URL sent to customer (message IDs stored in order.payment_message_ids)
8. APScheduler auto-cancels unpaid orders after 30 min
```

### Payment Completion (PayOS path)

```
9.  Customer pays → PayOS POSTs to /api/payos/webhook
10. FastAPI verifies HMAC-SHA256 signature
11. Webhook runs IPNOrderProcessor.process_payment_success() in thread executor
12. Processor: validates amount, updates status=PAID, deletes payment messages
13. Processor calls DeliveryService.process_paid_order()
14. Delivery routing:
    - PRE_UPLOADED → send text + .txt file to customer, status=DELIVERED
    - UPGRADE       → send account-info prompt, status=PROCESSING, await reply
15. OrderNotificationService sends admin notification
```

### Admin Dashboard Flow

```
Admin → React SPA → POST /api/auth/login → JWT token
JWT in Authorization header → FastAPI routes
Routes → Service layer → SQLAlchemy → PostgreSQL
```
