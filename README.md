# Bot Order System

## What it does

Bot Order System is a self-hosted Telegram storefront for digital products. Customers browse products, pay through PayOS QR or stored balance, and receive pre-uploaded inventory through the bot. Operators manage products, inventory, orders, balances, notifications, and runtime identity through a web dashboard.

Vietnamese is the default language. English is available from the bot language menu.

## Supported stack

The supported Docker Compose deployment contains exactly four services:

- `postgres` — PostgreSQL 16 and the only supported database.
- `api` — FastAPI dashboard API, PayOS webhook, and database migrations.
- `bot` — customer Telegram bot and delivery worker.
- `frontend` — React dashboard served by nginx.

PayOS is the only supported payment provider. Docker Compose is the only supported runtime path.

## Requirements

A Linux host with Git, Bash, Docker Engine, and the Docker Compose v2 plugin is the release-tested path. The host needs at least 1 GiB of free disk space plus capacity for PostgreSQL, backups, and delivery inventory. You also need a Telegram bot and numeric owner ID, PayOS merchant credentials, and public HTTPS frontend/API endpoints for production.

See [Installation](docs/INSTALLATION.md) for platform notes and credential preparation.

## Quick start

After cloning the repository, run:

```bash
chmod +x setup.sh manage.sh
./setup.sh
./manage.sh status
```

The wizard writes a mode-`600` `.env`, starts the stack, applies migrations, and creates the first dashboard administrator and runtime settings. It does not ship default credentials. Keep the generated `.env` private.

## First login and PayOS webhook

Open the frontend URL printed by `setup.sh` and sign in with the administrator credentials you entered. Review **General Settings** before accepting orders, especially the bot URL, timezone, support lines, order prefix, and API documentation URL.

Register this exact URL in the PayOS merchant dashboard:

```text
https://your-api.example/api/payos/webhook
```

The API must be publicly reachable over HTTPS. Test a sandbox payment before enabling real orders.

## Routine operations

Use `./manage.sh` for supported lifecycle operations. Common checks are:

```bash
./manage.sh doctor
./manage.sh logs bot
./manage.sh backup
```

Read [Operations](OPERATIONS.md) before updates, restores, or credential rotation.

## Experimental supplier code

Supplier-related source remains in the repository for future stabilization, but it is experimental and unsupported. It is not included in `setup.sh`, Docker Compose, health checks, or mounted dashboard routes. Do not present or enable it as a production runtime without a separate security and migration review.

## Documentation

- [Installation](docs/INSTALLATION.md) — host preparation, setup prompts, first-run verification, and uninstall boundaries.
- [Configuration](docs/CONFIGURATION.md) — complete deployment environment and runtime settings reference.
- [Architecture](docs/ARCHITECTURE.md) — services, trust boundaries, persistence, and payment flows.
- [Operations](OPERATIONS.md) — lifecycle commands, backup/restore, monitoring, and troubleshooting.
- [Security policy](SECURITY.md) — supported versions, private reporting, and secret handling.
- [Code of Conduct](CODE_OF_CONDUCT.md) — community standards and enforcement.
- [Roadmap](ROADMAP.md) — release milestones and post-v1 priorities.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

Licensed under the [GNU Affero General Public License version 3](LICENSE).
