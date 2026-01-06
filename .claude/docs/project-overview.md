# Project Overview - MTK Bot Order System

**Last Updated:** 2025-01-XX

---

## Project Summary

MTK_BOT_ORDER is a Telegram bot-based order system that allows users to browse products, place orders, and receive deliveries through an interactive single-message interface. The system integrates with Pay2S payment gateway and supports two delivery types: instant pre-uploaded products and supplier-based manual delivery.

---

## Key Features

### User Features
- **Product Browsing**: Paginated product list with inline keyboard navigation
- **Product Selection**: View product details, variations, prices, and stock
- **Order Creation**: Select variations, adjust quantities, and proceed to payment
- **Payment Integration**: Seamless Pay2S payment gateway integration
- **Instant Delivery**: Pre-uploaded products delivered immediately after payment
- **Supplier Delivery**: Supplier-based products delivered via supplier bot

### Admin Features
- **Order Statistics**: View order metrics and analytics
- **Product Management**: CRUD operations for products
- **Pre-uploaded Product Upload**: Bulk upload product data
- **Variation Management**: Configure product variations and pricing
- **Product Detail Management**: Edit product information

### Supplier Features
- **Order Notifications**: Receive order notifications via supplier bot
- **Product Delivery**: Reply with product data to complete delivery

---

## Technology Stack

- **Language**: Python 3.11+
- **Bot Framework**: python-telegram-bot 20.0+
- **Web Framework**: Flask 2.3+
- **Database**: SQLite
- **ORM**: SQLAlchemy 2.0
- **Payment**: Pay2S (already implemented)
- **State Management**: Redis (production) / in-memory (development)

---

## Project Structure

```
MTK_BOT_ORDER/
├── src/
│   ├── bot/              # Telegram bot (to be implemented)
│   ├── database/         # Database models and services (to be implemented)
│   ├── delivery/         # Delivery system (to be implemented)
│   ├── supplier_bot/     # Supplier bot (to be implemented)
│   ├── dashboard/        # Admin dashboard (to be implemented)
│   └── pay2s/            # Payment integration (✅ already implemented)
├── config/               # Configuration files
├── tests/                # Test files
├── .claude/              # Claude Code configuration
│   ├── plans/           # Implementation plans
│   ├── docs/            # Project documentation
│   └── agents/         # Agent configurations
└── requirements.txt      # Python dependencies
```

---

## Implementation Plan

See `.claude/plans/telegram-bot-order-system.md` for the complete implementation plan with:
- Detailed database schema
- User flow diagrams
- 7 implementation phases
- Task breakdown
- Testing strategy
- Security considerations

---

## Key Documents

1. **CURSOR.md** - Coding standards and best practices
2. **.claude/tech-stack.md** - Technology stack reference
3. **.claude/plans/telegram-bot-order-system.md** - Implementation plan
4. **README.md** - Project setup and usage

---

## Development Workflow

1. **Read** `.claude/plans/telegram-bot-order-system.md` for requirements
2. **Follow** TDD approach (write tests first)
3. **Use** existing patterns from `src/pay2s/` as reference
4. **Follow** coding standards in `CURSOR.md`
5. **Run** quality gates before committing (typecheck, lint, test, build)

---

## Next Steps

1. Review the implementation plan
2. Set up development environment
3. Start with Phase 1: Core Infrastructure
4. Follow TDD for all implementations

---

**End of Overview**

