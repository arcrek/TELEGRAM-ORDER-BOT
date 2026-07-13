# Repository Agent Guide

## Public release contract

Bot Order System is a self-hosted Telegram digital storefront. The supported deployment is Docker Compose-only and contains exactly `postgres`, `api`, `bot`, and `frontend`. PostgreSQL is the only supported database and PayOS is the only supported payment provider. Vietnamese is the default language; English is available.

Supplier source is experimental. It is absent from setup, Compose, health checks, and mounted API routes. Do not enable or document it as supported runtime work without an explicit supplier-stabilization task.

## Authoritative documentation

- [README.md](README.md) — public five-minute entry point.
- [docs/INSTALLATION.md](docs/INSTALLATION.md) — host and first-run procedure.
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) — complete environment and App Settings inventory.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — trust, persistence, and payment flows.
- [OPERATIONS.md](OPERATIONS.md) — supported lifecycle and recovery commands.
- [CONTRIBUTING.md](CONTRIBUTING.md) — branch, code, test, and pull-request rules.

Update the canonical document for an interface instead of copying instructions into another guide.

## Supported commands

```bash
chmod +x setup.sh manage.sh
./setup.sh
./manage.sh start
./manage.sh stop
./manage.sh restart
./manage.sh status
./manage.sh logs [api|bot|frontend|postgres]
./manage.sh doctor
./manage.sh backup [name]
./manage.sh restore FILE
./manage.sh update
./manage.sh help
```

Do not replace these public interfaces with raw multi-process startup instructions. Raw Compose operations belong only in the break-glass boundary documented in `OPERATIONS.md`.

## Code boundaries

- `src/bot/` contains the async customer Telegram interface. Preserve i18n and edit-in-place message behavior.
- `src/dashboard/` contains FastAPI routes. Use Pydantic at request/response boundaries and preserve authentication roles.
- `src/database/services/` owns database business logic. New handlers/routes must not query or mutate models directly.
- `src/database/models/` owns SQLAlchemy models. Every schema change requires an Alembic migration.
- `src/ipn/processor.py` is the shared PayOS/balance fulfillment path. Preserve exact amount checks, the `TU` top-up dispatch invariant, and idempotence.
- `frontend/` is the React/TypeScript dashboard. `VITE_API_BASE_URL` is compiled at image build time.

Deployment secrets live in `.env` and are never dashboard-editable. The seven non-secret App Settings live in PostgreSQL and are editable at runtime through General Settings.

## Verification

Use the smallest relevant check during development, then run the applicable release checks:

```bash
pytest
ruff check .
mypy src
cd frontend
npm test -- --run
npm run lint
npm run build
```

For deployment-interface changes also render Compose with a temporary synthetic env and verify `./manage.sh doctor` on a clean Linux host. Never create a repository `.env` for tests.

## Repository safety

Preserve unrelated work in a dirty tree. Never commit `.env`, credentials, database data/dumps, backups, customer records, payment payloads, or delivery inventory. Do not modify tables manually, force-push, or run destructive Git commands unless the task explicitly authorizes them.
