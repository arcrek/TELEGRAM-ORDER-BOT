# Backend Architecture

## Service Layer Pattern

All business logic lives in `src/database/services/`. Handlers and routes never access SQLAlchemy models directly — they call service methods and receive plain Python objects or dicts.

```python
# Pattern used everywhere
service = ProductService(session)
products = service.list_products(page=1, per_page=15)
```

Each service receives a `Session` in its constructor (never creates its own session).

## Key Services

| Service | Responsibility |
|---------|---------------|
| `OrderService` | Create, update, list orders; update status; cancel |
| `ProductService` | CRUD for products; list with pagination/search/sort |
| `VariationService` | Product variation CRUD |
| `DeliveryService` | Determine delivery type; `process_paid_order()` |
| `PreUploadedService` | Inventory management; `deliver_order()` allocates stock and returns content |
| `BonusTierService` | Compute bonus quantity from tiers |
| `DiscountTierService` | Compute discount amount from tiers |
| `OrderNotificationService` | Send ORDER_PAID notifications to admin channels |
| `AutoCancelService` | Bulk-cancel overdue pending orders |
| `UserPreferenceService` | Per-user language preference |
| `BotAdminService` | Read/write bot admin Telegram IDs from DB |
| `NotificationSettingsService` | Broadcast target channels/chats |
| `BotUISettingsService` | Bot welcome message + UI text |

## Bot Handler Architecture

`src/bot/main.py` registers handlers in **handler groups** (0, 1, 2):

- **Group 0** (default): Command handlers + most callback handlers + `handle_products_button`
- **Group 1**: `handle_custom_quantity_input` — separate group so it runs even when group 0's `handle_products_button` matches
- **Group 2**: `handle_upgrade_message` — catches all non-command messages for UPGRADE delivery forwarding

Handler group ordering is critical. Changing registration order or groups breaks the custom-quantity and UPGRADE flows.

### State Management

`src/bot/states/state_manager.py` holds a dict keyed by `user_id`. States are in-memory, not persisted — restarting the bot loses all in-progress sessions.

Common state keys: `waiting_custom_quantity`, `current_product_id`, `current_variation_id`, `current_quantity`, `current_order_id`.

### Single-Message Pattern

The bot edits the existing message (via `message.edit_text()` or `query.edit_message_text()`) rather than sending new ones, to keep the chat clean. The only exceptions are delivery messages and payment QR codes.

## Payment Flow

### PayOS (Primary)

1. `src/payos/client.py` — `PayOSClient.create_payment_link(order_code, amount, items)` — POST to PayOS API with HMAC-SHA256 signed payload
2. QR image generated via `qrcode` + `Pillow`
3. Bot stores message IDs of payment messages in `order.payment_message_ids` (JSON array)
4. PayOS sends webhook → `src/dashboard/routers/payos_webhook.py`
5. Webhook verifies checksum, calls `IPNOrderProcessor.process_payment_success()` in thread executor, passing the current asyncio loop via `request_loop=` param

### Pay2S (Secondary)

1. `src/pay2s/payment.py` — `create_payment()` — POST to Pay2S API with HMAC-SHA256 signature
2. Pay2S sends callback → `src/pay2s/ipn.py` Flask app at `/api/pay2s/ipn`
3. IPN verifies signature via `src/pay2s/signature.py`, calls `get_ipn_processor().process_payment_success()`

### IPN Processor (`src/ipn/processor.py`)

Core class: `IPNOrderProcessor`. Runs synchronously (called from sync IPN handler or from async FastAPI via thread executor).

`run_async(coro)` helper handles three contexts:
- **Worker thread with running loop** (PayOS FastAPI path): uses `asyncio.run_coroutine_threadsafe`
- **Sync context with no running loop** (Pay2S Flask path): `loop.run_until_complete()`
- **Async caller on loop thread** (edge case): spins up a new loop in a `ThreadPoolExecutor`

### Delivery Logic

After payment confirmed:
1. Delete payment messages from Telegram
2. Call `DeliveryService.process_paid_order(order_id)` — marks items as allocated
3. Route by `delivery_type`:
   - **PRE_UPLOADED**: `PreUploadedService.deliver_order()` → allocates stock → `_send_pre_uploaded_products()` sends text + `.txt` file
   - **UPGRADE**: sends account-info prompt to customer, sets `order.awaiting_upgrade_info = True`
   - **SUPPLIER_BASED**: disabled — sends error message to customer

## Bonus & Discount System

### BonusTier (buy-X-get-Y)

- Attached per variation via `ProductVariation.benefit_mode`
- `benefit_mode = bonus | discount | both`
- Tier selection: highest `min_quantity` tier that the order quantity meets
- Bonus items added to `order_item.bonus_quantity`

### DiscountTier

- Two `discount_type` values: `percentage` (5 = 5% off), `fixed_price` (override unit price in VND)
- Applied similarly — highest qualifying tier wins
- Savings stored in `order_item.discount_amount`

## Background Jobs

`src/bot/tasks/auto_cancel_task.py` — `AutoCancelTask`

- Runs every **5 minutes** via APScheduler `BackgroundScheduler`
- Calls `AutoCancelService.cancel_overdue_orders()` — cancels orders in `PENDING` status older than 30 min
- Cancellation sends Telegram notification to user

## UPGRADE Delivery Flow (detailed)

1. Payment confirmed → `_handle_upgrade_delivery()` sends prompt message to customer
2. `order.awaiting_upgrade_info = True`, `order.upgrade_prompt_msg_id = <msg_id>` saved
3. Customer replies (any text/photo/document) to that specific message
4. `src/bot/handlers/upgrade_handler.py` → `handle_upgrade_message()` intercepts the reply
5. Reply forwarded to each `upgrade_forwards` chat (notification channels in `NotificationSettings`)
6. Admin replies in notification chat → `handle_upgrade_message()` relays reply back to customer
7. Admin can mark order done via `upgrade_done_<order_id>` callback → order status = DELIVERED

## Global State (risks)

`src/ipn/processor.py` maintains two module-level globals:
- `_global_bot` — customer bot instance
- `_global_supplier_bot` — supplier bot instance (currently unused)

These are set by `src/bot/main.py` at startup via `set_global_bot()`. If the IPN server runs in a separate container (Pay2S path), it creates fresh `Bot()` instances from env vars instead.

`src/bot/states/state_manager.py` holds in-memory state dict — not thread-safe for high concurrency, but acceptable for single-process polling bot.
