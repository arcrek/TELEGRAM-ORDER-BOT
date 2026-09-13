# Documentation Index

Bot Order System is a self-hosted Telegram storefront for digital products. The supported production deployment is Docker Compose-only, PostgreSQL-only, PayOS-only, and contains exactly four services: `postgres`, `api`, `bot`, and `frontend`.

This directory houses the deployment, configuration, and architectural guides. Operational and contribution policies reside at the repository root.

## In This Directory

- [Installation](INSTALLATION.md) — Host preparation, Docker Compose prerequisites, setup wizard walkthrough, PayOS webhook registration, first-run verification, and uninstall / data-retention boundaries.
- [Configuration](CONFIGURATION.md) — Complete environment variable reference (`.env`), deployment secrets, and the seven runtime App Settings managed via the dashboard.
- [Architecture](ARCHITECTURE.md) — Four-service graph, network and trust boundaries, persistence and volume ownership, order and balance flows, PayOS webhook verification, the `TU` top-up dispatch invariant, and experimental supplier boundaries.

## Root Operational & Governance Guides

- [System Overview](../README.md) — Product summary, service stack, requirements, and five-minute quickstart.
- [Operations](../OPERATIONS.md) — Supported `./manage.sh` lifecycle commands, automated backup creation, non-destructive restore, quarterly restore drills, health monitoring, credential rotation, and symptom-driven troubleshooting.
- [Contributing](../CONTRIBUTING.md) — Development setup, branch workflow, backend/bot conventions, test execution, and pull request checklist.
- [Security Policy](../SECURITY.md) — Supported versions, private vulnerability reporting, and credential handling.
- [Roadmap](../ROADMAP.md) — Release criteria for the `v0.1.0` beta candidate, `v1.0.0`, and post-v1 milestones.
- [Code of Conduct](../CODE_OF_CONDUCT.md) — Community standards, pledge, and enforcement responsibilities.
- [Agent Guide](../AGENTS.md) — Canonical rules, safety boundaries, and constraints for AI contributors.
- [Claude Guide](../CLAUDE.md) — Pointer to `AGENTS.md` and repository operating invariants.

## Subsystem Guides

- [Frontend Dashboard](../frontend/README.md) — Local development, testing, and linting for the React dashboard.
- [Repository Scripts](../scripts/README.md) — Low-level helper scripts invoked by `setup.sh` and `manage.sh`.
