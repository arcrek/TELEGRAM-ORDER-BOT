# API Reference

Base URL (local): `http://localhost:8001`  
Interactive docs: `http://localhost:8001/docs`

## Authentication

All routes (except `/api/auth/login`, `/health`, `/`) require a Bearer token:

```
Authorization: Bearer <jwt_token>
```

Tokens expire after **24 hours**. Obtain via `POST /api/auth/login`.

**Roles:**
- `admin` — full read/write access
- `viewer` — read-only; write routes return 403

Rate limit on login: **5 requests/minute per IP**.

---

## Auth Endpoints

### `POST /api/auth/login`
Login and receive a JWT token.

**Request** (form data, `application/x-www-form-urlencoded`):
```
username=admin&password=admin123
```

**Response 200:**
```json
{"access_token": "<jwt>", "token_type": "bearer"}
```

**Response 401:** Invalid credentials  
**Response 429:** Rate limit exceeded

---

### `GET /api/auth/me`
Returns current admin info.

**Response 200:**
```json
{
  "id": "admin_abc12345",
  "username": "admin",
  "email": null,
  "full_name": "Admin User",
  "role": "admin",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00"
}
```

---

### `POST /api/auth/register`
Create a new admin user. **Admin role required.**

**Request body:**
```json
{
  "username": "newadmin",
  "password": "secret",
  "full_name": "New Admin",
  "role": "viewer"
}
```

---

## Products

### `GET /api/products`
List products with pagination, search, sort.

**Query params:**
| Param | Default | Description |
|-------|---------|-------------|
| page | 1 | Page number |
| per_page | 15 | Max 100 |
| search | — | Search name/description |
| only_active | — | true/false filter |
| sort_by | name | `name` or `created_at` |
| sort_order | asc | `asc` or `desc` |

**Response 200:**
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "per_page": 15,
  "pages": 3
}
```

---

### `POST /api/products`
Create a product. **Admin role.**

**Request body:**
```json
{
  "id": "netflix-premium",
  "name": "Netflix Premium",
  "description": "1-month account",
  "delivery_type": "pre_uploaded",
  "is_active": true
}
```

`delivery_type` values: `pre_uploaded`, `supplier_based`, `upgrade`

---

### `GET /api/products/{product_id}`
Get single product with variations.

### `PUT /api/products/{product_id}`
Update product fields (partial update).

### `DELETE /api/products/{product_id}`
Delete product. **Admin role.**

---

## Orders

### `GET /api/orders`
List orders with filters.

**Query params:**
| Param | Description |
|-------|-------------|
| page, per_page | Pagination |
| status | `pending`, `paid`, `processing`, `delivered`, `cancelled` |
| user_id | Filter by Telegram user ID |
| product_id | Filter by product |
| search | Search order ID |
| sort_by | `created_at`, `total_amount`, `status` |
| sort_order | `asc` / `desc` |
| start_date, end_date | ISO 8601 date range |

---

### `GET /api/orders/{order_id}`
Get order detail with items.

### `PATCH /api/orders/{order_id}/status`
Update order status. **Admin role.**

```json
{"status": "delivered"}
```

### `GET /api/orders/export`
Export orders as CSV (same filters as list).

---

## Variations

### `GET /api/variations?product_id=<id>`
List variations for a product.

### `POST /api/variations`
Create variation.
```json
{
  "id": "netflix-1m",
  "product_id": "netflix-premium",
  "name": "1 Month",
  "price": 150000,
  "stock": -1,
  "benefit_mode": "discount",
  "is_active": true
}
```

`stock`: -1 = unlimited  
`benefit_mode`: `bonus`, `discount`, or `both`

### `PUT /api/variations/{variation_id}`
Update variation.

### `DELETE /api/variations/{variation_id}`
Delete variation. **Admin role.**

---

## Bonus Tiers

### `GET /api/bonus-tiers?variation_id=<id>`
### `POST /api/bonus-tiers`
```json
{"variation_id": "...", "min_quantity": 10, "bonus_quantity": 2}
```
### `PUT /api/bonus-tiers/{tier_id}`
### `DELETE /api/bonus-tiers/{tier_id}`

---

## Discount Tiers

### `GET /api/discount-tiers?variation_id=<id>`
### `POST /api/discount-tiers`
```json
{
  "variation_id": "...",
  "min_quantity": 5,
  "discount_type": "percentage",
  "discount_value": 10
}
```
`discount_type`: `percentage` (0-100) or `fixed_price` (VND override)

### `PUT /api/discount-tiers/{tier_id}`
### `DELETE /api/discount-tiers/{tier_id}`

---

## Pre-Uploaded Products

### `GET /api/pre-uploaded?product_id=<id>&variation_id=<id>`
List pre-uploaded inventory.

### `POST /api/pre-uploaded`
Add single item to inventory.
```json
{
  "product_id": "netflix-premium",
  "variation_id": "netflix-1m",
  "delivery_data": "email:pass123"
}
```

### `POST /api/products/{product_id}/upload`
Bulk upload via CSV file (multipart form). **Admin role.**

### `DELETE /api/pre-uploaded/{item_id}`
### `DELETE /api/pre-uploaded/bulk`
Bulk delete by IDs.

---

## Statistics

### `GET /api/statistics/overview`
Returns counts: total orders, revenue, active users, product count.

### `GET /api/statistics/orders?days=30`
Order volume by day for the last N days.

### `GET /api/statistics/revenue?days=30`
Revenue by day.

### `GET /api/statistics/top-products?limit=10`
Top selling products by revenue.

---

## Notifications

### `GET /api/notifications/settings`
Get notification settings (chat IDs, upgrade targets).

### `PUT /api/notifications/settings`
Update settings. **Admin role.**

### `POST /api/notifications/broadcast`
Send broadcast message to all or active users. **Admin role.**
```json
{"message": "🎉 Special offer today!", "target": "all"}
```
`target`: `all` or `active`

---

## Bot UI Settings

### `GET /api/bot-ui-settings`
### `PUT /api/bot-ui-settings`
Update welcome message and UI text. **Admin role.**

---

## PayOS Webhook

### `POST /api/payos/webhook`
Called by PayOS after successful payment. Not for manual use.

Verifies HMAC-SHA256 signature using `PAYOS_CHECKSUM_KEY`, then calls `IPNOrderProcessor.process_payment_success()`.

---

## Image of the Day (IOTD)

### `GET /api/iotd`
### `PUT /api/iotd`
### `DELETE /api/iotd`

---

## Health Check

### `GET /health`
Returns `{"status": "healthy"}`. No auth required. Used by Docker healthcheck.

### `GET /`
Returns API name and version.
