# Operations

Run all supported operator commands from the repository root after completing `./setup.sh`. `manage.sh` reads the root `.env`, operates the four configured services, and returns nonzero when a required precondition or health check fails.

## `./manage.sh start`

Starts existing service images in the background and waits up to two minutes for API readiness. It requires `.env` and a valid Compose configuration.

Expected behavior: service startup output followed by exit `0` when `GET /ready` succeeds. It exits nonzero with `API readiness failed` when the API/database does not become ready; inspect `./manage.sh logs api`. This command does not rebuild images.

## `./manage.sh stop`

Stops all four services without removing containers, bind-mounted data, delivery inventory, or backups.

Expected behavior: stop progress and exit `0`. Missing/invalid `.env` or a stop failure returns nonzero. Use this for planned maintenance, not as an uninstall.

## `./manage.sh restart`

Builds images, force-recreates the services, and waits for API readiness. Persistent database and delivery storage remain intact.

Expected behavior: build/recreate output and exit `0` after readiness. A build, start, or readiness failure returns nonzero; the message distinguishes readiness failure after restart. Use it after changing `.env`, Dockerfiles, backend dependencies, or the frontend API build argument.

## `./manage.sh status`

Prints the current service table and then verifies API/database readiness.

Expected behavior: the table contains `postgres`, `api`, `bot`, and `frontend`; exit `0` means the API readiness endpoint reached PostgreSQL. Containers can be listed while readiness still fails, in which case the command exits nonzero with `containers are present but API/database is not ready`.

## `./manage.sh logs [service]`

Follows the last 200 log lines for all services, or for one of `postgres`, `api`, `bot`, or `frontend`.

Expected behavior: the command continues following until interrupted. An omitted service follows all four. An unknown service exits nonzero before reading logs. An interactive Ctrl-C normally produces the shell's interrupt exit status; that does not indicate an application failure.

Use the narrowest useful stream:

```bash
./manage.sh logs api
./manage.sh logs bot
```

API logs contain migrations, HTTP requests, readiness failures, and PayOS webhook decisions. Bot logs contain Telegram polling, payment-link creation, scheduled cancellation, and delivery results. Never paste raw logs into an issue without removing tokens, customer data, payment payloads, and inventory.

## `./manage.sh doctor`

Checks the Docker CLI, daemon, Compose plugin, `.env` existence and mode `600`, Compose rendering, at least 1 GiB free disk, all configured services running, PostgreSQL readiness, and API readiness.

Expected behavior: one `[ok]` or `[fail]` line per check. Exit `0` means every check passed; exit `1` means at least one failed. The diagnostic continues after individual failures so one run shows the full host state. On native macOS, the permissions check requires GNU `stat` support.

Run it after installation, upgrades, restores, host reboots, and credential rotation.

## `./manage.sh backup [name]`

Creates a PostgreSQL plain SQL dump under `backups/`. Without a name, the UTC filename is `backup_YYYYMMDD_HHMMSS.sql`; a supplied name may contain only letters, digits, dots, underscores, and hyphens.

The script writes with mode-restrictive umask to a temporary file, requires a non-empty dump, and atomically renames it to the final path. It prints only the final relative path on success and exits `0`. Invalid names, database failures, or empty output return nonzero and remove the temporary file.

The dump uses clean/drop statements so it can replace existing objects during restore. A successful command proves a dump was written, not that it is restorable; follow the drill policy below.

## `./manage.sh restore FILE`

Restores a non-empty SQL dump into the configured database. This is destructive to current database objects.

The command requires the exact interactive confirmation `RESTORE`. Any other response prints `Restore cancelled` and exits `0` without changing data. After confirmation it stops `bot` and `api`, starts PostgreSQL, waits up to one minute for database readiness, restores with stop-on-error, and starts `api`, `bot`, and `frontend`.

The command exits `0` only when the SQL restore, final start of `api`, `bot`, and `frontend`, and final API/database readiness check succeed. Afterward, run:

```bash
./manage.sh status
./manage.sh doctor
```

An invalid/empty file, database timeout, or SQL error returns nonzero. If restore fails after services stop, correct the cause and deliberately recover; do not assume the previous application state resumed.

## `./manage.sh update`

Performs the supported source update path:

1. Validate `.env` and Compose configuration.
2. Refuse unstaged or staged tracked changes.
3. Record the current commit.
4. Create an atomic `pre_update_UTC_TIMESTAMP` database backup.
5. Print the backup path and previous commit.
6. Fetch only a fast-forward update from the configured Git upstream.
7. Rebuild/start the services and wait for readiness.

The backup is created before any network update or rebuild. Exit `0` means the pull, rebuild, and readiness check completed. Dirty tracked files, backup failure, a non-fast-forward pull, build error, or readiness failure returns nonzero. Every pull, build, or readiness failure after the backup prints the previous commit and backup path; the script does not roll back automatically. Ignored `.env`, backups, and bind-mounted data are left untouched.

Read release notes and verify backup retention before running an update. Do not update when the current checkout contains uncommitted operator patches.

## `./manage.sh help`

Prints the command summary. Missing command, `help`, `-h`, and `--help` all show help and exit `0`; it does not require `.env` or Docker. Any other unknown command prints an error directing the operator to help and exits nonzero.

## Backup retention and off-host copies

The scripts never prune backups. Define a capacity-aware policy and automate it outside the repository. A reasonable minimum for an active installation is seven daily, four weekly, and twelve monthly verified backups, plus the most recent pre-update backup. Regulatory or customer requirements may demand longer retention.

Keep at least one encrypted copy off the application host and restrict access as tightly as `.env`. A database dump contains administrator records, customer/order history, balances, and pre-uploaded inventory. The Docker-managed `delivery_data` volume contains only transient generated files for interrupted deliveries; it is not the authoritative inventory store and is not included in the SQL dump.

Record the creation time, application commit, size, checksum, encryption location, and last restore result for each retained backup. Delete expired copies securely according to the operator's data-retention policy.

## Quarterly restore drill

At least once per quarter and before a major update:

1. Create a fresh named backup and record its checksum and current commit.
2. Copy the dump to a disposable, access-controlled rehearsal host with a separate `.env` and no production Telegram polling or public PayOS webhook.
3. Run `./manage.sh restore FILE`, then `./manage.sh status` and `./manage.sh doctor`.
4. Sign in, inspect representative orders/balances/settings, and verify row counts or business records chosen before the drill.
5. Record duration, result, errors, and remediation; destroy the rehearsal copy securely.

Do not run a drill against the only production database. A retained dump without a successful restore drill is an unverified backup.

## Health endpoints and monitoring

The API exposes:

- `GET /health` — dependency-free liveness; returns `200 {"status":"healthy"}` when the FastAPI process responds.
- `GET /ready` — database readiness; returns `200 {"status":"ready"}` after `SELECT 1`, or `503 {"detail":"database unavailable"}` on database failure.

Monitor both through the public API path, alert on repeated non-2xx responses, and also alert when `./manage.sh doctor` fails. A healthy endpoint does not prove Telegram or PayOS connectivity; monitor bot/API logs and perform a low-value sandbox transaction after relevant changes.

## Credential rotation

Schedule a maintenance window, create a backup, and keep the old credential active only until the replacement is verified.

- **Telegram token:** revoke/regenerate it with BotFather, update `TELEGRAM_BOT_TOKEN` in `.env`, run `./manage.sh restart`, and verify `/start`. Revocation interrupts the old bot immediately.
- **PayOS keys:** rotate the client/API/checksum keys in the merchant dashboard, update all three `.env` values together, restart, confirm the registered webhook path, and complete a sandbox payment. Mismatched checksum keys cause callbacks to be acknowledged but skipped, so inspect API logs.
- **Dashboard signing key:** replace `DASHBOARD_SECRET_KEY` with a strong random value and restart. All existing bearer tokens become invalid; sign in again.
- **PostgreSQL password:** change the live role password and `DB_PASSWORD` in the same window, then restart and run doctor. Editing `.env` alone does not change an initialized PostgreSQL role; the interactive database step is documented only in the break-glass section.
- **Bot owner ID:** update `BOT_OWNER_TELEGRAM_ID`, restart, and verify the new owner can list bot administrators before considering the old owner removed.

The current public API has no supported dashboard password-change, account-list, deactivation, or recovery operation. For a suspected dashboard-admin compromise, restrict public access and coordinate a supported recovery change rather than editing PostgreSQL directly.

## Dashboard and Telegram administrators

`setup.sh` creates the first dashboard administrator from operator-supplied credentials; no default account exists. An authenticated dashboard administrator can create another `admin` or `viewer` with `POST /api/auth/register` through the API documentation. The endpoint does not expose passwords after creation. Account retirement is not yet a supported API operation, so provision additional accounts deliberately.

The Telegram owner is configured by `BOT_OWNER_TELEGRAM_ID` and cannot be removed through the bot. Telegram administrator commands are:

```text
/setadmin list
/setadmin <numeric-id-or-username>
/setadmin remove <numeric-id-or-username>
```

Any Telegram administrator may list the set. Only the configured owner may add or remove database-backed administrators. Username lookup works only after that user is known to the bot; numeric Telegram IDs are unambiguous.

Dashboard administrators and Telegram administrators are separate authorization systems. Adding an identity to one does not grant access to the other.

## Symptom-driven troubleshooting

### `doctor` says `.env permissions are 600` failed

Restrict the root `.env` to its owner, rerun doctor, and verify no backup or copy has broader permissions. On native macOS, confirm GNU `stat` is installed before treating this single check as a file-mode failure.

### `status` lists containers but readiness fails

Read `./manage.sh logs api`, then `./manage.sh logs postgres`. Common causes are failed migrations, mismatched database credentials, an unhealthy database, or full disk. Do not repeatedly restart a migration failure without preserving its first error.

### Frontend loads but API calls fail

Check the browser network error, the public API certificate, `CORS_ORIGINS`, and `VITE_API_BASE_URL`. Changing the frontend API URL requires `./manage.sh restart` so the frontend image is rebuilt.

### Telegram bot does not answer `/start`

Run doctor, then inspect bot logs. Verify the token, outbound network access, and that only this deployment is polling the bot. After token rotation, restart before testing.

### PayOS reports webhook delivery but the order remains pending

Inspect API logs for missing configuration, invalid signature, non-success code, unknown order code, amount mismatch, or processor failure. The webhook intentionally returns HTTP 2xx for many rejected payloads, so the PayOS delivery status alone is insufficient.

### Top-up is paid but balance is unchanged

Search API logs by PayOS order code and internal `TU` ID. Confirm the callback amount exactly matches the stored top-up. Do not credit manually until the idempotent top-up status and balance transaction have been inspected.

### Backup is empty or fails

Confirm PostgreSQL is healthy, there is free space, and `backups/` is writable. The script removes incomplete temporary files. Resolve the database/storage cause and create a new backup; do not retain a zero-byte artifact.

### Restore stops services and exits nonzero

Preserve the failing SQL error, database logs, original dump, and current backup. Correct compatibility or storage issues before retrying. Run status and doctor only after SQL restore succeeds.

## Break-glass: raw Compose boundary

The commands below bypass parts of `manage.sh` and are not normal operations. Use them only when the supported wrapper cannot perform a necessary diagnostic or live PostgreSQL credential rotation. Create a verified backup first, work from the repository root, record every action, and never add an experimental service.

Read-only emergency inspection:

```bash
docker compose ps
docker compose config --services
docker compose logs --tail=200 api
```

Interactive PostgreSQL role-password rotation (the prompt keeps the new password out of command history):

```bash
docker compose exec postgres sh -c 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

At the `psql` prompt run `\password`, exit, update `DB_PASSWORD` in `.env`, and return immediately to `./manage.sh restart` followed by `./manage.sh doctor`.

Do not use raw Compose to delete persistent volumes or bind mounts, skip backups, run schema changes, or start source-tree services outside the supported four-service graph.
