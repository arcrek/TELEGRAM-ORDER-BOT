# Repository scripts

The supported public interfaces are root `setup.sh` for installation and `manage.sh` for lifecycle, diagnostics, backup, restore, and updates. Follow [Installation](../docs/INSTALLATION.md) and [Operations](../OPERATIONS.md); do not duplicate an installation path here.

## Called by supported wrappers

- `bootstrap_system.py` reads one JSON payload from standard input and creates the first dashboard administrator and App Settings in one transaction. Reruns preserve existing bootstrap records. `setup.sh` is its public caller.
- `backup_database.sh` writes an atomic, non-empty PostgreSQL SQL dump under `backups/`. Use `./manage.sh backup [name]`.
- `restore_database.sh` requires a non-empty dump and exact interactive `RESTORE` confirmation. Use `./manage.sh restore FILE` and run status/doctor afterward.

These scripts resolve the repository root themselves and read database identity inside the PostgreSQL container. Do not pass credentials on command lines or commit their output.

## Development and controlled maintenance

- `create_admin.py` creates an administrator through `AdminService` with a hidden prompt or password on standard input. Normal deployments create the first account through setup and additional accounts through authenticated `POST /api/auth/register`.

All scripts must preserve the service-layer database boundary and must not embed credentials, operator identity, production domains, customer data, or delivery inventory.
