# Open-Source Bootstrap and Operations Design

**Status:** Approved

**Date:** 2026-07-13

## Purpose

Prepare MTK Bot Order System for an AGPL-3.0 open-source release that a new
operator can install, configure, run, update, and recover without reading the
source code. Docker Compose is the only supported deployment path. PayOS is
the only supported external payment provider.

The work also removes current operator-specific credentials, identities, and
branding from tracked files. The public release will use a sanitized snapshot
with fresh Git history; the existing repository and its history remain
private.

## Current-State Problems

The current repository cannot be published safely or onboard a new operator
reliably:

- Tracked Python and Docker Compose files contain live-looking Pay2S
  credentials.
- A Telegram user ID is hard-coded as an irrevocable super-admin.
- A personal account handle, phone number, and production brand are used as
  application defaults.
- Pay2S and PayOS branches coexist even though the target system uses PayOS
  only.
- The disabled Pay2S IPN service, Flask application, Dockerfile, dependencies,
  tests, and documentation remain in the repository.
- The supplier subsystem is present but its dashboard routes and Compose
  service are disabled.
- `README.md`, `OPERATIONS.md`, `.env.example`, and Docker Compose disagree
  about the database, enabled services, payment provider, and setup process.
- The first-admin script exposes an insecure default username/password and can
  receive passwords through process arguments.
- Docker startup does not make PostgreSQL readiness an explicit prerequisite
  for API migrations.
- Existing backup scripts silently use default database names unless the host
  shell happens to export matching values.
- Project governance files required for a public project are absent.

## Goals

1. Provide one supported `./setup.sh` path from clone to a verified running
   Docker Compose system.
2. Provide one `./manage.sh` entry point for normal system operations.
3. Make every operator-specific value discoverable and give it one clear
   source of truth.
4. Keep deployment secrets outside the database and editable runtime identity
   fields inside the existing General Settings feature.
5. Remove all executable Pay2S support while preserving shared fulfillment
   behavior and historical order reporting.
6. Publish detailed installation, configuration, architecture, operations,
   contribution, security, and roadmap documentation.
7. Make setup, bootstrap, updates, backups, restores, and health checks fail
   safely with actionable output.

## Non-Goals

- Native Python/Node installation is not supported.
- Kubernetes, Helm, cloud-specific deployment, and automatic TLS are not part
  of the first public release.
- The setup script does not provision DNS, certificates, Telegram bots, or a
  PayOS merchant account.
- The supplier subsystem is not repaired or supported in the first release.
- The setup script is not a browser-based wizard.
- The application does not edit its own `.env` file from the dashboard.
- Existing private Git history will not be cleaned for publication; the public
  repository starts from a sanitized snapshot.

## Supported Runtime

The default Compose project contains four supported application services:

| Service | Responsibility | Public exposure |
| --- | --- | --- |
| `postgres` | Persistent PostgreSQL database | No public exposure by default |
| `api` | FastAPI dashboard API, migrations, and PayOS webhook | Public HTTPS through operator infrastructure |
| `bot` | Customer Telegram bot and scheduled jobs | Outbound Telegram/API traffic only |
| `frontend` | React dashboard served by nginx | Public HTTPS through operator infrastructure |

The PayOS webhook remains in the FastAPI process at
`/api/payos/webhook`; there is no standalone IPN container.

The supplier source remains in `src/bot_supplier/` and related database
modules. It is excluded from `setup.sh`, the default Compose stack, health
criteria, and normal installation instructions. Documentation labels it
experimental and unsupported.

## Configuration Ownership

Each setting has one authoritative home.

### Deployment and secret settings

These values live in the root `.env`, are consumed by Docker Compose, and
require a service restart when changed:

| Group | Settings | Notes |
| --- | --- | --- |
| Telegram | `TELEGRAM_BOT_TOKEN`, `BOT_OWNER_TELEGRAM_ID` | Owner ID replaces the hard-coded super-admin identity |
| PostgreSQL | `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Password is generated during setup unless explicitly supplied |
| PayOS | `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` | All three are required; optional partner metadata is omitted unless the active client requires it |
| Dashboard security | `DASHBOARD_SECRET_KEY` | Generated with at least 256 bits of entropy |
| Public routing | `FRONTEND_URL`, `VITE_API_BASE_URL`, `CORS_ORIGINS` | Canonical frontend/API URLs and explicit HTTPS origins in production; wildcards remain forbidden |
| Host ports | `DASHBOARD_PORT`, `FRONTEND_PORT` | Defaults remain documented and may be changed before startup |

`.env.example` is the canonical inventory. It contains safe empty values and
clearly labeled development defaults only. It never contains a real identity,
credential, account number, domain, or phone number. The generated `.env` is
written atomically with permission mode `0600` and remains ignored by Git and
Docker build context.

Standard vendor endpoints that operators should not change are code defaults,
not installation questions. PayOS return and cancel behavior uses the runtime
bot link described below. The setup completion message prints the derived
webhook URL that the operator must register in PayOS.

### Runtime operator settings

The existing `AppSettings` singleton, service, authenticated API, and General
Settings dashboard page are extended with:

| Field | Validation | Runtime behavior |
| --- | --- | --- |
| `system_name` | Required, trimmed, 1-80 characters | Used in bot copy, delivery output, API identity, and dashboard branding |
| `bot_url` | Required `https://t.me/...` URL | Used for PayOS return/cancel links and operator-facing links |
| `support_line_1` | Optional, at most 200 characters | First customer support footer line |
| `support_line_2` | Optional, at most 200 characters | Second customer support footer line |
| `timezone` | Valid IANA timezone | Reuses current `zoneinfo` validation and bot display behavior |
| `order_prefix` | 2-8 uppercase ASCII letters or digits | Applies only to newly created human-readable order IDs |
| `api_docs_url` | Empty or absolute HTTPS URL | Used by the bot API-token help command |

The authenticated General Settings endpoint returns all fields. A separate
unauthenticated public response exposes only `system_name`, allowing the login
screen and dashboard shell to display operator branding without exposing
support or administrative configuration.

Database-backed notification settings, bot UI prompts, products, additional
Telegram bot administrators, and dashboard users stay in their existing
models and dashboard areas.

### Administrative identities

The first dashboard administrator and the Telegram bot owner are distinct:

- `BOT_OWNER_TELEGRAM_ID` is required deployment configuration. That identity
  always has bot-admin access and is the only identity allowed to add or remove
  database-backed bot administrators.
- Additional Telegram bot administrators remain in `bot_admins`.
- Dashboard administrators remain in `admins` and are created through the
  secure bootstrap command or authenticated dashboard API.

No numeric identity is compiled into the source. Invalid or absent owner
configuration fails closed for bot-admin commands and produces a clear startup
diagnostic.

## PayOS-Only Simplification

The following Pay2S-only artifacts are deleted:

- `src/pay2s/`
- the Pay2S-only `config/` package
- `Dockerfile.ipn`
- `wsgi.py`
- Pay2S-only tests
- Pay2S environment variables and Compose sections
- Flask and Gunicorn dependencies when no remaining import needs them
- Pay2S setup, operations, troubleshooting, and architecture documentation

Product-order and top-up handlers lose provider selection and Pay2S fallback
branches. They create PayOS links directly and validate only the PayOS
credentials. The shared `src/ipn/processor.py` fulfillment path remains
because it is used by PayOS webhooks and balance-paid orders; only its Pay2S
wording is removed.

No migration deletes or rewrites historical `payment_provider` values. Revenue
statistics count paid external-QR orders generically rather than enumerating
old provider names, so existing private deployments retain historical totals
without keeping an executable Pay2S integration.

## `setup.sh` Design

### Platform and interface

`setup.sh` is an interactive Bash script for Linux, macOS, and WSL. The only
product prerequisites are Git, Docker Engine/Desktop, and the Docker Compose
plugin. It runs only from the repository root and prints `./manage.sh help`
when installation succeeds.

The script prompts in four groups:

1. Public URLs and optional host-port overrides.
2. Telegram bot token and Telegram owner ID.
3. PayOS client ID, API key, and checksum key.
4. Initial system identity and dashboard administrator details.

Database and dashboard signing secrets are generated automatically. Secret
input and the dashboard password use hidden terminal input and confirmation.
The dashboard password must be at least 12 characters. Values written to
`.env` reject newlines and characters outside the documented format.

### First-run flow

1. Resolve the repository root and install cleanup/error traps.
2. Check `git`, `docker`, and `docker compose` availability.
3. Confirm the Docker daemon is reachable.
4. Collect and validate input without writing partial state.
5. Set `umask 077`, render `.env` to a temporary file, validate that file with
   `docker compose config`, and atomically rename it to `.env`.
6. Start `postgres` and wait for its health check.
7. Build and start `api`; its existing entrypoint runs `alembic upgrade head`.
8. Wait for API readiness, including a database query.
9. Pipe a JSON bootstrap payload to a container-side Python command through
   stdin. The password never appears in the command line or log output.
10. Start `bot` and `frontend`.
11. Verify supported service state and API readiness.
12. Print the dashboard URL, API documentation URL, Telegram bot URL, exact
    PayOS webhook URL, and the next operational commands.

Compose adds a PostgreSQL health check and makes API startup depend on healthy
PostgreSQL. Bot startup continues to depend on a ready API. The API exposes a
liveness response that requires no dependencies and a readiness response that
checks database connectivity and completed startup.

### Safe reruns

An existing `.env` is never overwritten. A rerun validates and reuses it,
starts missing services, and resumes bootstrap only when required records do
not exist. Existing dashboard passwords, App Settings values, and bot-admin
records are not reset. Operators change runtime identity in General Settings;
they change deployment values by editing `.env` and running
`./manage.sh restart`.

The container-side bootstrap operation is transactional. On a fresh database
it creates the first administrator and initial App Settings together or rolls
back. On a resumed installation it creates only missing records and preserves
all existing records. If a dashboard administrator already exists, bootstrap
reports that fact and does not create a second privileged user.

## `manage.sh` Design

`manage.sh` is the only documented lifecycle interface. It resolves the
repository root before running Compose and supports:

| Command | Behavior |
| --- | --- |
| `start` | Validate configuration and run `docker compose up -d` |
| `stop` | Gracefully stop supported services without deleting data |
| `restart` | Rebuild and recreate services with current `.env`, then verify readiness |
| `status` | Show Compose state and fail nonzero when PostgreSQL/API readiness fails |
| `logs [service]` | Follow all logs or one validated supported service |
| `doctor` | Check prerequisites, `.env`, Compose rendering, disk availability, container state, database, and API readiness |
| `backup [name]` | Create a timestamped PostgreSQL SQL backup using container-side database environment values |
| `restore <file>` | Validate the backup, require an exact destructive confirmation, stop application writers, restore, restart, and verify |
| `update` | Preflight, backup, fast-forward source update, rebuild, migrate, start, and verify |
| `help` | Print commands and examples |

`update` refuses to run when tracked files have local changes. It leaves
ignored `.env`, backups, and persistent data untouched. Before fetching code,
it creates a verified database backup and records the current commit. It uses
`git pull --ff-only`, rebuilds images, starts the stack, and waits for
readiness. On failure it reports the previous commit and backup path. It does
not automatically roll back code or database migrations because a downgrade
may be destructive or incompatible.

Backup output is written to a temporary file and renamed only after `pg_dump`
succeeds and the result is non-empty. Restore never uses host defaults for
custom database names or users. PostgreSQL identifiers come from the running
container's trusted environment and are quoted by the restore implementation.

## Failure and Security Behavior

- Shell scripts use strict error handling and clean temporary files on exit.
- Secret values are never printed, included in process arguments, written to
  Git-tracked files, or included in diagnostics.
- Missing required settings fail before containers are changed.
- Invalid CORS wildcards, URLs, Telegram IDs, timezones, and order prefixes
  produce field-specific messages.
- Setup preserves a valid existing `.env`; it never partially rewrites it.
- Bootstrap database changes use a single transaction.
- Restore requires the operator to type an exact confirmation phrase.
- Update requires a clean tracked worktree and a successful backup.
- Health failures return nonzero exit codes suitable for automation.
- The API health endpoints disclose no credentials or database details.

## Documentation Set

The public repository contains one authoritative document per concern:

- `README.md`: overview, supported features, requirements, five-minute setup,
  service URLs, and links to deeper documentation.
- `docs/INSTALLATION.md`: BotFather setup, PayOS credentials, public HTTPS/DNS,
  every setup prompt, webhook registration, first login, and verification.
- `docs/CONFIGURATION.md`: a complete table of environment and runtime fields
  with source, requirement, secrecy, validation, default, editing method, and
  restart effect.
- `OPERATIONS.md`: every `manage.sh` command, normal updates, backups, restore
  drills, monitoring, credential rotation, admin management, and
  troubleshooting.
- `docs/ARCHITECTURE.md`: supported services, trust boundaries, database access,
  order/top-up/payment flows, fulfillment, and persistent storage.
- `SECURITY.md`: supported versions, private reporting process, secret-handling
  policy, disclosure expectations, and credential-rotation guidance.
- `CONTRIBUTING.md`: Docker development setup, migrations, tests, style, commit
  expectations, and pull-request checklist.
- `CODE_OF_CONDUCT.md`: Contributor Covenant text and the repository's private
  GitHub reporting path for enforcement contact.
- `ROADMAP.md`: supported milestones and explicitly experimental work.
- `LICENSE`: complete AGPL-3.0 license text.

Supplier functionality appears only in an experimental section that states it
is excluded from setup, default Compose, support commitments, and release
acceptance testing.

## Publication Safety

The public repository is created from the final sanitized working tree as a
new Git repository. The current repository, including its historical secrets,
remains private and is never pushed to the public remote.

Before creating the public snapshot, the operator must revoke or rotate every
credential that appeared in tracked history, including the removed Pay2S
credentials. The final snapshot is scanned for high-entropy secrets, known
credential patterns, private keys, `.env` files, database files, backups,
delivery data, personal contact information, and owner IDs.

CI blocks publication and pull requests on:

- backend tests
- backend lint after the existing baseline is clean
- frontend tests and production build
- shell syntax and behavior checks
- Docker Compose rendering with safe test configuration
- secret scanning
- dependency/license policy checks compatible with AGPL-3.0 distribution

The release is licensed under AGPL-3.0. The README explains the network-use
source-sharing obligation without attempting to replace legal advice.

## Test Strategy

### Application tests

- App Settings model/service/API tests cover defaults, validation, authorized
  updates, and the limited public response.
- Handler tests prove product orders and top-ups take the PayOS path with no
  provider selector.
- PayOS webhook tests retain signature rejection, idempotency, amount checks,
  order fulfillment, and balance top-up coverage.
- Telegram admin tests cover configured owner access, database admin access,
  invalid configuration, and owner-only administrator mutation.
- Statistics tests prove external QR history remains counted without a Pay2S
  runtime branch.
- Bootstrap tests cover first creation, duplicate rerun, transaction rollback,
  password stdin, and secret-free output.
- Readiness tests cover healthy database and unavailable database responses.

### Shell and Compose tests

Existing pytest is used to run scripts with fake `docker`, `git`, and Compose
executables placed first in `PATH`; no shell test framework is added. Coverage
includes missing prerequisites, invalid input, atomic `.env` creation, existing
`.env` reuse, command dispatch, dirty-worktree update rejection, backup-before-
pull ordering, update failure reporting, and destructive restore confirmation.

`bash -n` checks both scripts. CI renders Compose with safe dummy values and
asserts the expected supported service set and dependency health conditions.

### Release rehearsal

A clean Linux host runs the documented path from clone through `setup.sh`.
Release acceptance requires:

1. Successful PayOS sandbox product purchase and fulfillment.
2. Successful PayOS sandbox top-up and balance credit.
3. Balance-paid order fulfillment.
4. Dashboard login and runtime identity update without rebuilding.
5. Successful backup and restore drill.
6. Successful no-op setup rerun.
7. Successful update rehearsal and a controlled failed-update rehearsal.

## Implementation Phases

### Phase 0: Publication blockers

Rotate exposed credentials, remove personal/operator defaults, add AGPL-3.0,
define the clean public snapshot procedure, and establish secret scanning.

**Exit criterion:** the intended public tree contains no credential, personal
operator value, private runtime data, or unlicensed project state.

### Phase 1: PayOS-only runtime

Delete Pay2S artifacts and dependencies, simplify payment handlers, retain the
shared fulfillment processor, and update statistics for generic historical QR
payments.

**Exit criterion:** product and top-up PayOS flows pass and no executable or
configurable Pay2S path remains.

### Phase 2: Centralized operator settings

Extend App Settings, add its migration and validation, connect all current
hard-coded consumers, expose limited public branding, and extend the General
Settings dashboard.

**Exit criterion:** operator-facing identity can be changed from the dashboard
without rebuilding or editing source.

### Phase 3: Reliable Docker bootstrap

Add PostgreSQL readiness ordering, API readiness, secure first-admin behavior,
transactional/idempotent bootstrap, and `setup.sh`.

**Exit criterion:** a clean supported host reaches a verified running system
through one interactive command.

### Phase 4: Lifecycle management

Add `manage.sh`, fix custom-database backup/restore behavior, and implement
safe start, stop, restart, status, logs, doctor, backup, restore, and update
flows.

**Exit criterion:** documented routine operation requires no raw Compose or
PostgreSQL commands.

### Phase 5: Documentation and governance

Replace contradictory documentation, add the complete public documentation
set and contribution policies, and make release CI blocking.

**Exit criterion:** an unfamiliar operator can install, configure, run,
update, back up, restore, and troubleshoot the supported system using only
public documentation.

### Phase 6: Release validation

Perform clean-host, PayOS sandbox, backup/restore, rerun, and update rehearsals;
scan the final snapshot; publish `v0.1.0` from fresh history.

**Exit criterion:** all automated gates and manual release acceptance checks
pass. Promote to `v1.0.0` after one stable operating cycle with no unresolved
release-blocking installation, payment, update, or recovery defect.

## Post-v1 Roadmap

1. Stabilize supplier workflows, restore their dashboard/API connections, add
   isolation tests, and only then offer an opt-in Compose profile.
2. Publish signed, versioned, multi-architecture container images so operators
   can update without local builds.
3. Add an optional reverse-proxy/TLS Compose profile after the base deployment
   remains stable.
4. Add guided credential rotation and audited dashboard-admin recovery.
5. Add release compatibility checks, migration previews, and supported release
   channels when upgrade volume justifies them.

## Acceptance Criteria

- A new operator installs the supported system with `./setup.sh` and no host
  Python or Node installation.
- `./manage.sh` covers every documented routine lifecycle action.
- PayOS and balance are the only executable payment paths.
- Supplier functionality is visibly experimental and absent from default
  installation and health checks.
- No tracked file contains operator credentials, identities, contact details,
  production domains, database data, backups, or delivery inventory.
- No dashboard or Telegram admin account has an insecure compiled default.
- Operator-facing identity is editable in General Settings and takes effect at
  runtime.
- The generated `.env` is secret-safe, canonical, validated, and never
  overwritten by setup reruns.
- Updates create a verified backup before changing code and fail closed on a
  dirty tracked worktree.
- Installation, configuration, operations, architecture, security,
  contribution, license, and roadmap documentation agree with the shipped
  Compose stack.
- The sanitized public snapshot passes all automated and manual release gates.
