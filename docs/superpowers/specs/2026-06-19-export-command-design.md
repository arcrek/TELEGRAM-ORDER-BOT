# `/export` Command — Design Spec

**Date:** 2026-06-19
**Status:** Approved (brainstorming) — pending implementation plan

## Summary

Add an `/export` feature to the **customer** Telegram bot that lets a user
download their purchased pre-uploaded content as plain-text files. The user
selects one product, toggles one or more of its variants, and the bot generates
one `.txt` file per selected variant containing every delivered order for that
product+variant (date, price, quantity, delivered content).

## Scope

**In scope**
- New `/export` command on the customer bot.
- Inline button on the `/start` menu.
- Button on the persistent reply keyboard.
- Multi-step, edit-in-place selection flow (product → variants → export).
- One `.txt` file per selected variant, sent via `send_document`.
- A dedicated `ExportService` for all data access.
- i18n strings (vi + en) for every user-facing string, including in-file labels.

**Out of scope (YAGNI)**
- Supplier-fulfilled products (no delivered content stored in DB).
- Any order status other than `DELIVERED`.
- CSV/spreadsheet/zip output formats.
- Export from the supplier bot or the dashboard.
- Selecting more than one product per `/export` run (re-run for another product).

## Constraints & invariants

- **Privacy (load-bearing):** every query is scoped to the requesting user's
  `telegram_user_id`. The export must never return `PreUploadedProduct` rows
  delivered to another user's orders — this is delivered account credentials.
- **Pre-uploaded only:** only products with delivered content stored in
  `pre_uploaded_products.product_data` are exportable.
- **`DELIVERED` only:** only orders with status `DELIVERED` are considered.
- **Edit-in-place:** the selection menus edit the existing bot message
  (CLAUDE.md convention). The generated `.txt` files are the one allowed
  exception — they are sent as new `send_document` messages.
- **No raw queries in handlers:** all DB access goes through `ExportService`.
- **All async:** handlers and service methods are `async`.

## Entry points

All three route to the same product-list handler:

1. **`/export` command** — `CommandHandler("export", ...)` registered in
   `src/bot/main.py` alongside the existing command handlers.
2. **`/start` inline button** — added to `_start_inline_keyboard()` in
   `src/bot/handlers/commands.py`, `callback_data="start_export"`, wired to a
   `CallbackQueryHandler(..., pattern="^start_export$")` in `main.py`.
3. **Reply-keyboard button** — added to `get_persistent_keyboard()` in
   `src/bot/utils/keyboard.py`; matched by button text in the message handler
   (same pattern as the existing "Order History" / "Products" buttons).

## Flow

1. **Product list.** Query the user's `DELIVERED` orders; keep only order items
   whose product is delivered via pre-uploaded content; reduce to distinct
   products. Render an inline keyboard, one button per product (callback carries
   the product id). If the user has no exportable products, show a friendly
   empty-state message and stop.
2. **Variant multi-select.** On product selection, list the distinct variants of
   that product the user has bought. Each variant is a toggle button
   (✅ when selected). Footer row: `[Export] [Back] [Cancel]`.
   - `Back` returns to the product list.
   - `Cancel` clears state and closes.
   - `Export` is a no-op (with a hint) if nothing is selected.
3. **Export.** For each selected variant, build a `.txt` and send it via
   `send_document`. After all files are sent, edit the menu message to a
   confirmation (e.g. "Exported N file(s)") and clear export state.

Because every exportable pre-uploaded row has a non-null `variation_id`, the
variant step always applies — there is no "product without variants" branch.

## File format (one file per variant)

Filename: `export_<product-slug>_<variant-slug>.txt` (sanitized; fall back to
ids if names are empty).

```
=== <Product name> / <Variant name> ===
Total orders: N | Total items: M

--- Order <order id> ---
Date: 2026-06-01 14:30
Price: 90,000 VND  Qty: 1
Delivered:
  <content line 1>

--- Order <order id> ---
Date: 2026-06-10 09:12
Price: 270,000 VND  Qty: 3
Delivered:
  <content line 1>
  <content line 2>
  <content line 3>
```

- **Header:** product name, variant name, then totals.
- **Total items (M):** counted from the actual delivered `PreUploadedProduct`
  rows, so `OrderItem.bonus_quantity` is included and not undercounted.
- **Per-order block:** order id, date, price, quantity, then each delivered
  content line indented under `Delivered:`.
- **Date:** rendered in the app timezone via `format_local`
  (`src/utils/datetime_format.py`).
- **Price:** VND with thousands separators, matching existing bot formatting.
- **Labels** (`Date:`, `Price:`, `Delivered:`, header totals): i18n to the
  user's language.

## Data access — `ExportService`

New module `src/database/services/export_service.py`. All methods user-scoped,
`DELIVERED`-only, pre-uploaded-only.

- `async get_exportable_products(user_id) -> list[...]`
  Distinct products the user has delivered pre-uploaded orders for.
- `async get_exportable_variations(user_id, product_id) -> list[...]`
  Distinct variants of that product the user has bought.
- `async get_variant_export(user_id, product_id, variation_id) -> ...`
  The data needed to render one file: product/variant names plus, per order,
  the order id, created_at, price paid, quantity, and the list of delivered
  content lines.

**Variant attribution (the join the feature rests on):** delivered content for a
variant comes from
`PreUploadedProduct WHERE used_by_order_id IN (<user's delivered orders>) AND variation_id = <variant>`.
Filtering on `variation_id` (not just `used_by_order_id`) prevents a
multi-variant order from leaking one variant's content into another variant's
file. Delivered content text is parsed from `product_data` via the existing
`PreUploadedService.get_product_data` parsing (JSON or plain text).

## State

Extend `UserState` in `src/bot/states/state_manager.py`:

- `export_product_id: Optional[str]` — product chosen in step 1.
- `export_selected_variation_ids: set[str]` — toggled variants in step 2.
- reuse/clear via the existing `update_user_state` / `clear_user_state`.

The selection-menu message id is tracked so the flow can edit in place
(reuse the existing message-id field convention).

## i18n

Add keys under a new `commands.export.*` namespace in both
`src/i18n/locales/vi/bot.json` and `src/i18n/locales/en/bot.json`:
command/button labels, product-list prompt, variant-select prompt, empty state,
export confirmation, and the in-file labels. Vietnamese is the default; no
hardcoded strings.

## Error handling & edge cases

- **No exportable products:** empty-state message, flow ends cleanly.
- **No variants selected on Export:** hint and stay on the variant screen.
- **A variant with zero delivered rows** (shouldn't occur given the query, but
  guard): skip the file and note it in the confirmation.
- **`send_document` failure:** log and report which files failed; do not crash
  the handler.
- **Large content:** files are plain text built in-memory (`BytesIO`), same
  pattern as the existing delivery `send_document` in `src/ipn/processor.py`.

## Testing

- `ExportService` unit tests: user-scoping (no cross-user leakage),
  pre-uploaded-only filtering, `DELIVERED`-only filtering, per-variant
  attribution for multi-variant orders, item count including `bonus_quantity`.
- File-builder test: header, totals, per-order blocks, label i18n.
- Handler/flow tests where the existing bot test harness allows: empty state,
  toggle behavior, export with one and multiple variants.

## Touched files (anticipated)

- `src/database/services/export_service.py` *(new)*
- `src/bot/handlers/` — new export handler module (+ wiring)
- `src/bot/main.py` — register command + callback handlers
- `src/bot/handlers/commands.py` — `/start` inline button
- `src/bot/utils/keyboard.py` — reply-keyboard button
- `src/bot/states/state_manager.py` — export state fields
- `src/i18n/locales/vi/bot.json`, `src/i18n/locales/en/bot.json` — strings
- `tests/` — service + builder + flow tests
