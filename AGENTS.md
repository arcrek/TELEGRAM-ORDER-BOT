# Repository Guidelines

## Project Structure & Module Organization
Core backend code lives under `src/`: `bot/` (customer Telegram bot), `bot_supplier/` (supplier bot), `dashboard/` (FastAPI API), `database/` (SQLAlchemy models, services, Alembic migrations), and payment/IPN modules (`pay2s/`, `payos/`, `ipn/`).
Frontend dashboard code is in `frontend/src/` with `components/`, `pages/`, `layouts/`, `contexts/`, and `test/`.
Integration and unit tests are in `tests/` (Python) and `frontend/src/test/` (Vitest). Operational scripts live in `scripts/`; runtime data is in `data/` and `delivery_data/`.

## Build, Test, and Development Commands
- `pip install -r requirements.txt`: install backend dependencies.
- `alembic upgrade head`: apply database migrations.
- `python -m src.bot.main`: run customer bot.
- `python -m src.bot_supplier.main`: run supplier bot.
- `python run_dashboard.py`: run FastAPI dashboard API (default `:8001`).
- `pytest` or `pytest --cov=src --cov-report=html`: run backend tests and coverage.
- `ruff check .`, `ruff format .`, `mypy src`: lint, format, and type-check backend.
- `cd frontend && npm install && npm run dev`: run frontend locally.
- `cd frontend && npm test`, `npm run lint`, `npm run build`: frontend test/lint/build.
- `docker compose up --build`: run full stack via containers.

## Coding Style & Naming Conventions
Python uses 4-space indentation, type hints for public functions, and `snake_case` for modules/functions/files. Keep service logic in `src/database/services/` and API routes in `src/dashboard/routers/`.
React/TypeScript uses `PascalCase` for components/pages (for example `OrdersPage.tsx`), `camelCase` for variables/functions, and colocated `.css` files for component/page styles.
Use `ruff format` for Python and `eslint` (`npm run lint`) for frontend checks before pushing.

## Testing Guidelines
Backend tests use `pytest` with files named `test_*.py` in `tests/`. Frontend tests use Vitest + Testing Library with `*.test.ts`/`*.test.tsx` in `frontend/src/test/`.
Prefer focused unit tests for new services/formatters and route-level tests for API behavior changes. Run both backend and frontend test suites when touching shared flows (orders, payments, notifications).

## Commit & Pull Request Guidelines
Recent history mixes conventional commits (`feat: ...`) and descriptive summaries. Standardize on concise, imperative subjects; prefer prefixes like `feat:`, `fix:`, `refactor:`, `test:`.
PRs should include: scope summary, linked issue/task, test evidence (commands run), migration notes if schema changes, and UI screenshots/GIFs for frontend updates.

## Security & Configuration Tips
Keep secrets in `.env`; never commit real tokens, payment keys, or production URLs. Validate new environment variables in `config/config.py` and document them in `README.md`.
For database changes, include an Alembic migration in `src/database/migrations/versions/` and verify upgrade/downgrade paths.
