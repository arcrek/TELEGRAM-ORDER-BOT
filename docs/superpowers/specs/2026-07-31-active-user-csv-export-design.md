# Active User CSV Export Design

## Goal

Let dashboard operators download every active Telegram user's username, name,
Telegram ID, and balance as a CSV file from the existing User Balances page.

## Design

- Add `GET /api/balances/export`, protected by the same viewer-or-admin access as
  the balance list.
- Fetch users through `BotUserService`, using the existing active-user definition:
  `is_active = true` and `has_started = true`.
- Return a UTF-8 CSV with a BOM and the columns `Username`, `Name`, `Telegram ID`,
  and `Balance`. Join first and last name with one space and leave missing values
  empty.
- Add an `Export CSV` action to the User Balances page. Download the response as
  `active_users_YYYY-MM-DD.csv` and show the existing toast error treatment if it
  fails.

## Verification

Add one API test proving that the endpoint requires authentication, excludes
inactive or not-started users, preserves Unicode names, and returns the required
columns and values. Run that test plus the frontend lint/build checks relevant to
the changed page.

## Non-goals

No generic export framework, pagination, background job, extra filters, or new
dependency. The export is a current snapshot of all active, started users.
