# CLAUDE.md

Read and follow [AGENTS.md](AGENTS.md); it is the canonical repository-agent guide.

The public runtime contract is Docker Compose-only, PayOS-only, PostgreSQL-only, and exactly four services: `postgres`, `api`, `bot`, and `frontend`. Start with `./setup.sh`; use `./manage.sh help` and the lifecycle commands documented in [OPERATIONS.md](OPERATIONS.md). Do not publish raw multi-terminal startup or default credentials.

Database business logic belongs in `src/database/services/`, model changes require Alembic migrations, bot UI text uses Vietnamese/English i18n, and bot interactions edit the existing message where possible. Deployment secrets stay in `.env`; runtime identity is edited through General Settings.

Supplier code under `src/bot_supplier/` and related models/services/routes is experimental, excluded from default setup and Compose, and must not be presented as supported.
