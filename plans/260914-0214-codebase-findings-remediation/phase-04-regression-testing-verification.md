# Phase 4: Regression Testing & Release Verification

**Status: Complete [x]**

## Overview
Develop targeted automated tests to guarantee regression safety for all remediated vulnerabilities, then run the full static analysis and verification pipeline.

## Scope of Work

### 1. Regression Test Suite
- **Files to Create:**
  - `tests/test_late_topup_remediation.py`:
    - Test auto-cancelled topup receives PayOS webhook $\rightarrow$ wallet balance credited properly, audit transaction created with `kind=TOPUP`, idempotent duplicate webhook handling.
  - `tests/test_bfla_rbac_security.py`:
    - Test client with `role="viewer"` receives `403 Forbidden` on:
      - `PUT /api/orders/{id}/status`
      - `POST /api/products`
      - `DELETE /api/products/{id}`
      - `POST /api/bonus-tiers`
      - `POST /api/discount-tiers`
      - `POST /api/product-upload/upload`
    - Test client with `role="admin"` succeeds on all above routes.
  - `tests/test_cancelled_order_resurrection.py`:
    - Test cancelled order receiving PayOS IPN returns False, logs alert, does not allocate unreserved inventory, and does not set status to `PAID`.
  - `tests/test_delivery_reentrancy.py`:
    - Test that calling `deliver_order` twice on the same order returns the already-marked products rather than consuming secondary stock rows.
  - `tests/test_api_token_privacy.py`:
    - Verify `GET /api/balances` payload does not expose `api_token` in user list items.

### 2. Full Verification Suite
- **Commands to Execute:**
  - `ruff check .` (must remain clean)
  - `pytest` (targeted regression suite + existing suite)

## Verification & Acceptance
- All newly authored regression tests pass with 0 failures.
- No existing tests broken.
- Static analysis clean.
