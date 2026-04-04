# Repository Guidelines

## Project Structure & Module Organization
- `src/` contains backend services:
- `src/bot/` customer Telegram bot, `src/bot_supplier/` supplier bot.
- `src/dashboard/` FastAPI admin API (`routers/` for endpoints, `auth.py` for JWT auth).
- `src/database/` SQLAlchemy models, service layer, and Alembic migrations (`migrations/versions/`).
- `src/ipn/`, `src/pay2s/`, and `src/payos/` handle payment/IPN workflows.
- `frontend/` is the React + TypeScript dashboard (`src/components`, `src/pages`, `src/test`).
- `tests/` holds Python test modules; `scripts/` stores operational scripts (admin creation, DB backup/restore).

## Build, Test, and Development Commands
- Install backend deps: `pip install -r requirements.txt`
- Run customer bot: `python -m src.bot.main`
- Run supplier bot: `python -m src.bot_supplier.main`
- Run dashboard API: `python run_dashboard.py`
- Run IPN server: `python run_ipn_server.py`
- Apply DB migrations: `alembic upgrade head`
- Run Python tests: `pytest` (or `./run_tests.sh`, `run_tests.bat`)
- Frontend setup: `cd frontend && npm install`
- Frontend dev server: `npm run dev`
- Frontend build: `npm run build`
- Frontend tests/lint: `npm test`, `npm run lint`

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints for new/edited service and API code, and `snake_case` for functions/modules.
- Enforce Python quality with `ruff check .`, `ruff format .`, and `mypy src` before PR.
- Frontend: TypeScript + React with `PascalCase` component files (for example `ProductsPage.tsx`), hooks/variables in `camelCase`.
- Keep API route modules focused by resource (`orders.py`, `suppliers.py`, etc.).

## Testing Guidelines
- Backend tests use `pytest` (+ `pytest-asyncio`, `pytest-cov`).
- Name Python tests as `tests/test_<feature>.py`; keep unit tests near related domain behavior.
- Frontend uses Vitest + Testing Library; place tests under `frontend/src/test/`.
- For meaningful backend changes, run `pytest --cov=src --cov-report=html` and include major coverage impact in PR notes.

## Commit & Pull Request Guidelines
- Existing history favors short, imperative commit subjects (for example `fix restore db`, `update entrypoint.sh`).
- Prefer `<area>: <action>` for clarity (example: `dashboard: add payos webhook validation`).
- Avoid vague commit titles like `.` or `typo` unless the change is truly trivial.
- PRs should include: purpose, changed modules, test commands run, migration/env changes, and UI screenshots for `frontend/` updates.
