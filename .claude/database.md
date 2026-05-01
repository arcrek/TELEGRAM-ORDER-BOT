# Database

## Connection Handling

File: `src/database/connection.py`

- **Singleton pattern**: One `Engine` and one `sessionmaker` at module level
- PostgreSQL pool: `pool_size=10`, `max_overflow=20`, `pool_recycle=1800s`, `pool_pre_ping=True`
- SQLite supported for tests (`check_same_thread=False`, no pool tuning)
- `get_db_session()` is a FastAPI generator dependency — yields a session and closes it in `finally`
- Tests pass an explicit engine to `get_session_factory(engine=...)` to get isolated sessions

URL resolution priority:
1. `DATABASE_URL` env var
2. `DB_HOST` + `DB_PORT` + `DB_NAME` + `DB_USER` + `DB_PASSWORD` env vars
3. `RuntimeError` if neither is set

## Schema Overview

### Core Tables

#### `products`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | human-readable slug |
| name | String | |
| description | Text | nullable |
| delivery_type | Enum | `pre_uploaded`, `supplier_based`, `upgrade` |
| upgrade_request_text | Text | custom prompt for UPGRADE delivery |
| is_active | Boolean | |

#### `product_variations`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | |
| product_id | String FK → products | |
| name | String | |
| price | Integer | VND |
| stock | Integer | -1 = unlimited |
| benefit_mode | String | `bonus`, `discount`, `both` |
| is_active | Boolean | |

#### `orders`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | |
| user_id | BigInteger | Telegram user ID |
| status | Enum | `pending`, `paid`, `processing`, `delivered`, `cancelled` |
| total_amount | Integer | post-discount VND |
| discount_amount | Integer | total savings |
| payment_provider | String | `payos` or `pay2s` |
| payment_transaction_id | String | Pay2S transaction ID |
| payment_message_ids | Text | JSON array of Telegram message IDs |
| payos_order_code | BigInteger | unique, PayOS-specific |
| payos_payment_link_id | String | |
| payos_checkout_url | Text | |
| awaiting_upgrade_info | Boolean | UPGRADE flow flag |
| upgrade_prompt_msg_id | BigInteger | Telegram message ID of the prompt |
| upgrade_forwards | Text | JSON — list of {chat_id, thread_id, header_msg_id, forward_msg_id} |

#### `order_items`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | |
| order_id | String FK → orders | cascade delete |
| product_id | String FK → products | |
| variation_id | String FK → product_variations | |
| quantity | Integer | ordered quantity |
| unit_price | Integer | price at time of order |
| bonus_quantity | Integer | extra items from BonusTier |
| discount_amount | Integer | savings from DiscountTier |

#### `pre_uploaded_products`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | |
| product_id | String FK → products | |
| variation_id | String FK | nullable |
| delivery_data | Text/JSON | account credentials, codes, etc. |
| is_delivered | Boolean | flipped after order delivery |
| order_id | String | set when delivered |

#### `bonus_tiers`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | |
| variation_id | String FK | |
| min_quantity | Integer | minimum purchase quantity |
| bonus_quantity | Integer | free items added |

#### `discount_tiers`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | |
| variation_id | String FK | |
| min_quantity | Integer | |
| discount_type | String | `percentage` or `fixed_price` |
| discount_value | Float | % or VND override |

### User & Admin Tables

#### `bot_users`
| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | Telegram user_id |
| username | String | Telegram username |
| first_name | String | |
| last_name | String | |
| created_at | DateTime | |
| last_active | DateTime | |

#### `user_preferences`
| Column | Type | Notes |
|--------|------|-------|
| user_id | BigInteger PK | |
| language | String | `vi` or `en` |

#### `admins`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | `admin_<hex8>` |
| username | String | unique |
| email | String | nullable |
| password_hash | String | bcrypt |
| full_name | String | |
| role | Enum | `admin` or `viewer` |
| is_active | Boolean | |
| last_login | DateTime | |

#### `bot_admins`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | |
| telegram_user_id | BigInteger | |
| added_at | DateTime | |

### Settings Tables

- `notification_settings` — broadcast chat IDs, upgrade notification chat IDs
- `bot_ui_settings` — welcome message text, button labels
- `iotd_settings` — Image of the Day media config

### Supplier Tables (disabled)

- `suppliers` — supplier master data
- `supplier_orders` — manual fulfillment records
- `product_supplier_assignments` — product→supplier mapping

## Key Relationships

```
Product 1──* ProductVariation
Product 1──* PreUploadedProduct
Product 1──* ProductSupplierAssignment

Order 1──* OrderItem
Order 1──* SupplierOrder

OrderItem *──1 Product
OrderItem *──1 ProductVariation

ProductVariation 1──* BonusTier
ProductVariation 1──* DiscountTier
ProductVariation 1──* PreUploadedProduct
```

## Migrations

```bash
alembic upgrade head           # apply all migrations
alembic revision --autogenerate -m "Description"  # create migration
alembic downgrade -1           # roll back one step
```

Migration files in: `src/database/migrations/versions/`
Alembic config: `alembic.ini` (script_location = `src/database/migrations`)

**Never modify table columns directly** — always create a migration.

## Potential Issues

- **Session not rolled back on partial error**: `IPNOrderProcessor` calls `session.rollback()` in the outer `except`, but delivery sub-methods can raise without triggering it if control flow exits via `finally`. Audit `_handle_pre_uploaded_delivery` carefully.
- **Delivery data in Text column**: `pre_uploaded_products.delivery_data` is stored as raw text/JSON in a `Text` column — no schema validation at the DB level.
- **upgrade_forwards stored as JSON Text**: Not a proper FK relation; relies on application-level parsing. If a notification chat is removed, stale entries remain.
- **In-memory session factory singletons**: Safe in single-process deployments. Would need review if multiple workers share the same process (e.g., gunicorn with multiple workers accessing `_SessionLocal`).
