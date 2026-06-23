# Task 12 Report: Customer Order Messages — Emoji Token Rendering

## Sites Wrapped

All sites reuse the **in-scope `session`** already open in their handler's `try` block — no new sessions needed.

### `src/bot/handlers/callbacks.py`

| Handler | Location (approx) | What was sent | Change |
|---|---|---|---|
| `handle_variation_selection` | ~386 | `formatter.format_order_confirmation(...)` — contains product.name, variation.name | `render_emoji(message, ...)` → `edit_message_text(rendered, parse_mode=parse_mode)` |
| `handle_quantity_adjustment` | ~470 | same formatter output | same pattern |
| `handle_custom_quantity_input` (edit + fallback send) | ~652–666 | same formatter output | rendered once before both the edit and the fallback send, both paths use `rendered`/`parse_mode` |
| `_create_qr_for_order` — PayOS text message | ~1116–1122 | `format_payment_message(...)` → full_message | rendered immediately after `format_payment_message`; both `edit_message_text` and `send_message` use `rendered_pm, pm_parse_mode` |
| `_create_qr_for_order` — PayOS QR photo caption | ~1132 | `caption` from `format_payment_message` | rendered separately as `rendered_caption, caption_parse_mode`; `send_photo(..., caption=rendered_caption, parse_mode=caption_parse_mode)` |
| `_create_qr_for_order` — PayOS QR fallback text | ~1148 | same `rendered_pm` | reused |
| `_create_qr_for_order` — PayOS no-QR fallback text | ~1160 | same `rendered_pm` | reused |
| `_create_qr_for_order` — Pay2S QR text message | ~1341–1344 | same `rendered_pm` | reused (rendered once above) |
| `_create_qr_for_order` — Pay2S QR photo caption | ~1353 | `caption_base + bank_info` (concatenated) | rendered **AFTER** concat: `render_emoji(caption_base + bank_info, ...)` |
| `_create_qr_for_order` — Pay2S no-QR text | ~1381 | `payment_message + bank_info + payment_url` (concatenated) | rendered **AFTER** full concat: `render_emoji(full_payment_message, ...)` |

### `src/bot/handlers/balance.py`

| Handler | Location (approx) | What was sent | Change |
|---|---|---|---|
| `handle_balance_button` | ~434 | balance view i18n text | `render_emoji(text, ...)` → `reply_text(rendered, parse_mode=parse_mode)` |
| `handle_balance_view` | ~461 | same balance view text | same pattern |
| `handle_balance_history` | ~653 | history lines (i18n) | `render_emoji("\n".join(lines), ...)` |
| `_create_topup_qr` — PayOS send_photo | ~244 | topup pending caption (i18n + amount/topup_id) | rendered once as `rendered_caption, caption_parse_mode`; used for all PayOS sends |
| `_create_topup_qr` — PayOS fallback send_message | ~252 | same | reused |
| `_create_topup_qr` — PayOS no-QR send_message | ~259 | same | reused |
| `_create_topup_qr` — Pay2S QR send_photo | ~369 | `caption + bank_info` | rendered **AFTER** concat |
| `_create_topup_qr` — Pay2S no-QR send_message | ~377 | `caption + payment_url` | rendered **AFTER** concat |

**Session scope decision (all sites):** Reused in-scope `session` already open in the handler's `try` block. No new sessions opened for rendering.

## Sites Intentionally Skipped

| Location | Reason |
|---|---|
| `callbacks.py` `handle_variation_selection` ~356: out-of-stock screen | Already sends `parse_mode="HTML"` with hand-built markup — skipped per brief rule |
| `callbacks.py` `handle_order_detail` ~1832 | Already sends `parse_mode="HTML"` with hand-built `html.escape`/`<code>` markup — skipped per brief rule |
| `upgrade_handler.py` ~217: `<pre>` block send | Already sends `parse_mode="HTML"` with hand-built `<pre>` — skipped per brief rule |
| `upgrade_handler.py` all other sends | Admin-relay via `copy_message`; not admin-authored product text |
| `callbacks.py` ~924: picker_text (payment method picker) | Transient message instantly replaced; contains only balance/total formatted numbers from i18n |
| `callbacks.py` ~1478–1551: balance-pay result messages | Pure i18n strings (success/insufficient/already_processed/generic), no admin text |
| `callbacks.py` ~1591–1628: cancel confirmation | Hard-coded static strings, no admin text |
| `callbacks.py` ~1911: language-changed | Pure i18n confirmation |
| `balance.py` ~473: topup_start title | Pure i18n, no admin text; also no open session at that point (session is not opened in handle_balance_topup_start) |
| `balance.py` ~532: custom topup prompt | Pure i18n; no session open at that point |
| `callbacks.py` error/validation/not-found sends | Trivial system messages, never contain admin text |
| `callbacks.py` order history list (1721/1868) | Product names live only in inline-button labels which can't carry custom emoji |

## Import Checks

- `python3 -c "import src.bot.main"` — clean (no output)
- `python3 -c "import src.bot.handlers.callbacks"` — clean (no output)
- `python3 -c "import src.bot.handlers.balance"` — clean (no output)

## Ruff

`ruff check src/bot/handlers/callbacks.py src/bot/handlers/balance.py`:
- **balance.py** — clean (0 issues)
- **callbacks.py** — 3 issues (F821 ×2, F841 ×1) — **pre-existing** before this task (confirmed by stashing changes and re-running ruff on unmodified file: same 3 issues). Not introduced by this task.

## Test Suite vs Baseline

`python3 -m pytest -q --ignore=tests/test_database_connection.py`:

**Result: 459 passed, 52 failed** — identical to documented baseline. No new failures.

(test_database_connection.py is excluded as it asserts a SQLite URL but the env is configured for PostgreSQL — pre-existing incompatibility.)

## Self-Review

**Escape-order invariant maintained:** Every site where `payment_message` or `caption` gets concatenated with bank info/payment URL uses `render_emoji(final_concatenated_string, ...)` — rendering happens AFTER all string assembly. This prevents HTML-unescaped appended content from breaking Telegram's HTML parser when a token is present.

**No-op guarantee for token-free text:** `render` returns `(text, None)` when no `{emo:` token is present, meaning all wrapped sites keep identical plain-text behavior for existing content.

**Caption parse_mode:** Every `send_photo` now passes `parse_mode=...` alongside its caption, matching the pattern used for text messages.

## Concerns

None. The implementation is conservative — it wraps customer-facing order/payment/balance messages where admin-authored product names flow through, applies the after-concat render rule on all concatenated strings, and leaves HTML-mode sites and trivial system messages untouched.
