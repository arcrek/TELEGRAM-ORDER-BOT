import io
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import scripts.bootstrap_system as bootstrap_module
from scripts.bootstrap_system import BootstrapPayload, bootstrap_system
from src.database.models import Admin
from src.database.models.app_settings import AppSettings
from src.database.models.base import Base


def payload() -> BootstrapPayload:
    return BootstrapPayload.model_validate(
        {
            "admin": {
                "username": "owner",
                "password": "long-password-123",
                "full_name": "System Owner",
                "email": "owner@example.com",
            },
            "settings": {
                "system_name": "Example Shop",
                "bot_url": "https://t.me/example_shop_bot",
                "support_line_1": "@support",
                "support_line_2": "",
                "timezone": "UTC",
                "order_prefix": "SHOP",
                "api_docs_url": "https://shop.example/api",
            },
        }
    )


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def run_main(monkeypatch, value):
    stdin = io.StringIO(json.dumps(value))
    stdout = io.StringIO()
    stderr = io.StringIO()
    engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(bootstrap_module, "create_engine_instance", lambda: engine)
    monkeypatch.setattr(bootstrap_module.sys, "stdin", stdin)
    monkeypatch.setattr(bootstrap_module.sys, "stdout", stdout)
    monkeypatch.setattr(bootstrap_module.sys, "stderr", stderr)
    try:
        return bootstrap_module.main(), stdout.getvalue(), stderr.getvalue()
    finally:
        engine.dispose()


def test_bootstrap_creates_admin_and_settings():
    db = session()
    result = bootstrap_system(db, payload())
    assert result == {"admin_created": True, "settings_created": True}
    assert db.query(Admin).one().username == "owner"
    assert db.query(AppSettings).one().system_name == "Example Shop"


def test_bootstrap_rerun_preserves_existing_records():
    db = session()
    bootstrap_system(db, payload())
    replacement = payload().model_copy(deep=True)
    replacement.admin.username = "replacement"
    replacement.settings.system_name = "Replacement Shop"
    result = bootstrap_system(db, replacement)
    assert result == {"admin_created": False, "settings_created": False}
    assert db.query(Admin).one().username == "owner"
    assert db.query(AppSettings).one().system_name == "Example Shop"


@pytest.mark.parametrize(
    ("existing", "expected"),
    [
        ("admin", {"admin_created": False, "settings_created": True}),
        ("settings", {"admin_created": True, "settings_created": False}),
    ],
)
def test_bootstrap_partial_rerun_creates_only_missing_side(existing, expected):
    db = session()
    if existing == "admin":
        db.add(
            Admin(
                id="existing-admin",
                username="existing",
                password_hash="existing-hash",
                full_name="Existing Admin",
            )
        )
    else:
        db.add(AppSettings(id="global", system_name="Existing Shop"))
    db.commit()

    assert bootstrap_system(db, payload()) == expected
    assert db.query(Admin).one().username == (
        "existing" if existing == "admin" else "owner"
    )
    assert db.query(AppSettings).one().system_name == (
        "Existing Shop" if existing == "settings" else "Example Shop"
    )


def test_invalid_payload_does_not_create_partial_records():
    db = session()
    invalid = payload().model_copy(deep=True)
    invalid.settings.order_prefix = "TU"
    try:
        bootstrap_system(db, invalid)
    except ValueError:
        pass
    assert db.query(Admin).count() == 0
    assert db.query(AppSettings).count() == 0


def test_query_failure_rolls_back():
    class FailingSession:
        rollback_called = False

        def query(self, *args):
            raise RuntimeError("query failed")

        def rollback(self):
            self.rollback_called = True

    db = FailingSession()
    with pytest.raises(RuntimeError, match="query failed"):
        bootstrap_system(db, payload())
    assert db.rollback_called is True


def test_cli_output_does_not_expose_password(monkeypatch):
    bootstrap_payload = payload().model_dump(mode="json")
    password = bootstrap_payload["admin"]["password"]
    return_code, stdout, stderr = run_main(monkeypatch, bootstrap_payload)
    assert return_code == 0, stderr
    assert json.loads(stdout) == {
        "admin_created": True,
        "settings_created": True,
    }
    assert password not in stdout
    assert password not in stderr


def test_cli_validation_error_exposes_only_field_path(monkeypatch):
    bootstrap_payload = payload().model_dump(mode="json")
    bootstrap_payload["admin"]["password"] = "secret"
    return_code, stdout, stderr = run_main(monkeypatch, bootstrap_payload)
    assert return_code != 0
    assert stdout == ""
    assert stderr.strip() == "admin.password"
    assert "secret" not in stderr
