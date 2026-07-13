# Contributing

Thank you for improving Bot Order System. By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through the private process in [SECURITY.md](SECURITY.md), not a public issue.

## Development setup

Use the supported Docker Compose installation first:

```bash
chmod +x setup.sh manage.sh
./setup.sh
./manage.sh doctor
```

The supported runtime remains exactly `postgres`, `api`, `bot`, and `frontend`. Do not add an always-on service or expose PostgreSQL as part of an unrelated contribution. Supplier source is experimental and excluded from default setup; changes there need an explicitly scoped proposal and must not imply production support.

For host-side tests and formatting, use Python 3.11+ and Node/npm versions compatible with the lockfile. Install Python requirements in a virtual environment and frontend dependencies with `npm ci`.

## Branches and scope

Create a short-lived feature branch from the current default branch. Keep each pull request focused on one behavior, include migrations and documentation with the behavior they support, and avoid drive-by reformatting or generated artifacts.

Prefer existing services, helpers, and platform features over new abstractions or dependencies. Explain any dependency addition and why the standard library or an installed package is insufficient.

## Backend conventions

- All database business access goes through `src/database/services/`; do not add model queries or mutations to bot handlers or dashboard routes.
- Every schema change includes a reversible Alembic migration. Never modify a production table manually or rely on ORM metadata creation as deployment migration.
- Keep bot handlers and service functions asynchronous where their interface is async, and add type hints to new functions.
- Use Pydantic request/response models at API boundaries and validate untrusted input there.
- Balance/payment transitions must remain atomic and idempotent. Add a focused regression test for any changed money path.

## Bot conventions

- Use the i18n catalogs under `src/i18n/locales/`; Vietnamese is the default and English must remain available. Do not hardcode new user-facing strings.
- Preserve the single-message interaction pattern: edit the existing bot message instead of sending a replacement when Telegram permits it.
- Check ownership and administrator authorization before reading or mutating user/order data.
- Keep the reserved `TU` top-up prefix distinct from configurable product-order prefixes.

## Checks

Run the smallest relevant test while developing, then the release-facing checks before requesting review:

```bash
pytest
ruff check .
mypy src
cd frontend
npm test -- --run
npm run lint
npm run build
```

If a command is unavailable in your environment, state exactly which check was not run and why. Do not report a check as passing without fresh output. Documentation-only changes should at minimum run link/structure checks and `git diff --check`.

## Secrets and test data

Never commit `.env`, database files or dumps, backups, private keys, Telegram tokens, PayOS credentials, dashboard signing keys, customer records, payment payloads, or delivery inventory. Use obviously synthetic values in tests and examples. If a real credential reaches Git history, rotate it immediately; deleting the current file is not remediation.

Do not upload production logs or screenshots without removing personal and transaction data. Keep generated coverage, build, cache, and editor files untracked.

## Pull-request checklist

- [ ] The branch and pull request address one explained problem.
- [ ] Database access stays in the service layer and schema changes include Alembic migration coverage.
- [ ] Payment/balance behavior remains atomic, amount-checked, and retry-safe.
- [ ] Bot text uses Vietnamese/English i18n and interactions preserve edit-in-place behavior.
- [ ] Relevant Python tests, lint/type checks, frontend tests/lint/build, and documentation checks pass, or omissions are disclosed.
- [ ] Public documentation and `.env.example` match any changed interface.
- [ ] No secret, personal data, database artifact, backup, or delivery inventory is included.
- [ ] Experimental supplier code is not presented as a supported runtime.
