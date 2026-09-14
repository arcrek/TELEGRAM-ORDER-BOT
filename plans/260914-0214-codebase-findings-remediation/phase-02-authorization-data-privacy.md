# Phase 2: Authorization & Data Privacy Hardening

**Status: Complete [x]**

## Overview
Enforce Role-Based Access Control (RBAC) across all state-mutating dashboard routes and prevent customer API token exposure.

## Scope of Work

### 1. Enforce `require_admin_role` Across All Dashboard Mutating Routes (`[CRIT-02]`)
- **Files:**
  - `src/dashboard/routers/orders.py`
  - `src/dashboard/routers/products.py`
  - `src/dashboard/routers/bonus_tiers.py`
  - `src/dashboard/routers/discount_tiers.py`
  - `src/dashboard/routers/product_upload.py`
  - `src/dashboard/routers/pre_uploaded.py`
- **Actions:**
  - Update imports: ensure `require_admin_role` is imported from `src.dashboard.auth`.
  - Replace `current_admin = Depends(get_current_admin)` with `current_admin = Depends(require_admin_role)` on:
    - `orders.py`: `update_order_status` (`PUT /{order_id}/status`)
    - `products.py`: `create_product` (`POST /`), `update_product` (`PUT /{product_id}`), `delete_product` (`DELETE /{product_id}`)
    - `bonus_tiers.py`: `create_bonus_tier` (`POST /`), `update_bonus_tier` (`PUT /{tier_id}`), `delete_bonus_tier` (`DELETE /{tier_id}`)
    - `discount_tiers.py`: `create_discount_tier` (`POST /`), `update_discount_tier` (`PUT /{tier_id}`), `delete_discount_tier` (`DELETE /{tier_id}`)
    - `product_upload.py`: `upload_excel` (`POST /upload`)
    - `pre_uploaded.py`: `delete_pre_uploaded` (`DELETE /{id}`)
  - Verify that read operations remain accessible to `require_viewer_or_admin` while mutations require `require_admin_role`.

### 2. Strip API Tokens from Customer Balance Serialization (`[CRIT-03]`)
- **Files:**
  - `src/database/services/balance_service.py`
  - `src/dashboard/routers/balances.py`
- **Actions:**
  - In `BalanceService.list_users_with_balance()`:
    - Remove `"api_token": user.api_token` from serialized item dict.
    - Alternatively, include only `has_api_token: bool(user.api_token)` if the UI requires an indicator of whether an API token is provisioned.
  - In `src/dashboard/routers/balances.py`:
    - Ensure no route leaks raw customer `api_token` strings to viewer accounts.

## Verification & Acceptance
- Authenticated requests with `role="viewer"` receive HTTP 403 Forbidden on all mutation routes.
- Authenticated requests with `role="admin"` continue to succeed on all mutation routes.
- `GET /api/balances` payload does not contain plaintext `api_token`.
