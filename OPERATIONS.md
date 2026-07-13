# Operations Command Reference

Run operator commands from the repository root. Complete initial configuration
with `./setup.sh` before managing the system.

| Command | Purpose |
| --- | --- |
| `./manage.sh start` | Start services and wait for API readiness. |
| `./manage.sh stop` | Stop services without deleting data. |
| `./manage.sh restart` | Rebuild, recreate, and verify services. |
| `./manage.sh status` | Show Compose state and verify readiness. |
| `./manage.sh logs [api\|bot\|frontend\|postgres]` | Follow the last 200 log lines. |
| `./manage.sh doctor` | Check Docker, configuration, disk, database, and API health. |
| `./manage.sh backup [name]` | Write an atomic SQL dump under `backups/`. |
| `./manage.sh restore backups/file.sql` | Replace the database after exact `RESTORE` confirmation. |
| `./manage.sh update` | Back up, fast-forward pull, rebuild, and verify. |
| `./manage.sh help` | Show the command summary; no `.env` or Docker required. |

## Safety notes

- `update` rejects unstaged or staged tracked changes. It prints the previous
  commit and backup path before `git pull --ff-only` and the Compose rebuild so
  an operator retains recovery information if a later step fails.
- `restore` accepts only a non-empty file and never rebuilds database names in
  SQL. The clean dump restores into the database configured inside PostgreSQL.
- Backup and restore read `POSTGRES_USER` and `POSTGRES_DB` inside the container;
  host shell database variables are ignored.
- Backups are excluded from Git. Copy important backups off the host.
