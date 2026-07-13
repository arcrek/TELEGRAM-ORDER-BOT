import importlib


def test_initial_migration_creates_admins(monkeypatch):
    migration = importlib.import_module(
        "src.database.migrations.versions.142d667a84ac_initial_migration_create_all_tables"
    )
    created_tables: list[str] = []

    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *args, **kwargs: created_tables.append(name),
    )

    migration.upgrade()

    assert "admins" in created_tables
