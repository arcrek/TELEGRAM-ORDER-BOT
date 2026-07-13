import json
import os
import subprocess
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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


def test_cli_output_does_not_expose_password(tmp_path):
    bootstrap_payload = payload().model_dump(mode="json")
    password = bootstrap_payload["admin"]["password"]
    result = subprocess.run(
        [sys.executable, "-m", "scripts.bootstrap_system"],
        input=json.dumps(bootstrap_payload),
        text=True,
        capture_output=True,
        env=os.environ | {"DATABASE_URL": f"sqlite:///{tmp_path / 'bootstrap.sqlite'}"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "admin_created": True,
        "settings_created": True,
    }
    assert password not in result.stdout
    assert password not in result.stderr


def test_cli_validation_error_exposes_only_field_path(tmp_path):
    bootstrap_payload = payload().model_dump(mode="json")
    bootstrap_payload["admin"]["password"] = "secret"
    result = subprocess.run(
        [sys.executable, "-m", "scripts.bootstrap_system"],
        input=json.dumps(bootstrap_payload),
        text=True,
        capture_output=True,
        env=os.environ | {"DATABASE_URL": f"sqlite:///{tmp_path / 'bootstrap.sqlite'}"},
        check=False,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.strip() == "admin.password"
    assert "secret" not in result.stderr
