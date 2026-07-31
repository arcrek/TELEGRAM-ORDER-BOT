# Active User CSV Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authenticated CSV download of every active, started Telegram user's username, full name, Telegram ID, and balance to the User Balances dashboard page.

**Architecture:** Extend the existing bot-user service with the ordered active-user query, then expose it through the existing balances router using Python's standard `csv` module. Reuse the Orders page's browser Blob download pattern in the Balances page.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, TypeScript, Axios, browser Blob API.

## Global Constraints

- Active means `is_active = true` and `has_started = true`.
- CSV columns are exactly `Username`, `Name`, `Telegram ID`, and `Balance`.
- CSV output uses a UTF-8 BOM; missing username/name values are empty cells.
- The filename is `active_users_YYYY-MM-DD.csv`.
- Add no dependency or generic export abstraction.

---

### Task 1: Authenticated active-user CSV endpoint

**Files:**
- Create: `tests/test_balances_export_api.py`
- Modify: `src/database/services/bot_user_service.py`
- Modify: `src/dashboard/routers/balances.py`

**Interfaces:**
- Produces: `BotUserService.get_active_users() -> list[BotUser]`, ordered by Telegram ID.
- Produces: `GET /api/balances/export` with `text/csv; charset=utf-8` content and attachment filename `active_users_export.csv`.

- [ ] **Step 1: Write the failing API test**

Create an isolated SQLite-backed TestClient test. Insert an authenticated admin and three `BotUser` rows: one active/started user named `Nguyễn Văn An`, one inactive/started user, and one active/not-started user. Assert an unauthenticated request returns `401`; authenticated output starts with `\ufeff`, parses to exactly:

```python
[
    ["Username", "Name", "Telegram ID", "Balance"],
    ["active_user", "Nguyễn Văn An", "1001", "125000"],
]
```

- [ ] **Step 2: Run the test to verify RED**

Run: `pytest tests/test_balances_export_api.py -q`

Expected: authenticated request fails with `404` because `/api/balances/export` does not exist.

- [ ] **Step 3: Implement the minimal endpoint**

Keep `get_active_users()` as the single database boundary and make its result deterministic:

```python
return (
    self.session.query(BotUser)
    .filter_by(is_active=True, has_started=True)
    .order_by(BotUser.telegram_user_id)
    .all()
)
```

Add `csv`, `io`, and FastAPI `Response` imports to the balances router. Define `/export` before `/{bot_user_id}` so the literal route wins. Write the header and each active user using:

```python
writer.writerow([
    user.username or "",
    " ".join(filter(None, [user.first_name, user.last_name])),
    user.telegram_user_id,
    user.balance,
])
```

Return `"\ufeff" + output.getvalue()` with media type `text/csv; charset=utf-8`, `Content-Disposition: attachment; filename=active_users_export.csv`, and `require_viewer_or_admin` authentication.

- [ ] **Step 4: Run the test to verify GREEN**

Run: `pytest tests/test_balances_export_api.py -q`

Expected: all tests pass.

### Task 2: User Balances download action

**Files:**
- Modify: `frontend/src/pages/BalancesPage.tsx`

**Interfaces:**
- Consumes: `GET /api/balances/export` as an Axios Blob response.
- Produces: an accessible `Export CSV` button that downloads `active_users_YYYY-MM-DD.csv`.

- [ ] **Step 1: Add the existing download pattern**

Import `Download`, `Button`, and `useToast`; initialize `toast`. Add a `handleExport` function that requests `/api/balances/export` with `responseType: 'blob'`, creates and clicks a temporary anchor, revokes the object URL, and reports errors through:

```typescript
toast.error(formatApiError(err, t('balances.exportError', 'Không thể xuất người dùng')))
```

- [ ] **Step 2: Add the header action**

Place the export button beside Refresh in `PageHeader.actions`, using the existing common translation key and accessible text:

```tsx
<Button
  variant="secondary"
  tone="subtle"
  size="sm"
  iconLeft={<Download size={14} />}
  onClick={handleExport}
>
  {t('common.export', 'Xuất CSV')}
</Button>
```

- [ ] **Step 3: Verify frontend types and lint**

Run: `cd frontend && npm run lint && npm run build`

Expected: both commands exit successfully.

### Task 3: Release-focused verification and commit

**Files:**
- Verify all files changed in Tasks 1-2.

**Interfaces:**
- Consumes: completed endpoint, API regression test, and dashboard action.
- Produces: verified feature commit on branch `old`.

- [ ] **Step 1: Run focused backend checks**

Run: `pytest tests/test_balances_export_api.py tests/test_bot_user_service.py -q`

Expected: all tests pass.

- [ ] **Step 2: Run static backend checks on changed modules**

Run: `ruff check src/dashboard/routers/balances.py src/database/services/bot_user_service.py tests/test_balances_export_api.py`

Expected: no lint errors.

- [ ] **Step 3: Review the diff**

Run: `git diff --check && git diff --stat && git status --short`

Expected: no whitespace errors and only the planned files are modified or created.

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/routers/balances.py src/database/services/bot_user_service.py frontend/src/pages/BalancesPage.tsx tests/test_balances_export_api.py docs/superpowers/plans/2026-07-31-active-user-csv-export.md
git commit -m "feat: export active users to CSV"
```
