"""Initialize the first dashboard admin and application settings from stdin."""

import json
import sys

from pydantic import BaseModel, EmailStr, Field, ValidationError
from sqlalchemy.orm import Session

from src.dashboard.auth import get_password_hash
from src.database.connection import (
    create_engine_instance,
    get_session_factory,
    init_database,
)
from src.database.models.admin import AdminRole
from src.database.services.admin_service import AdminService
from src.database.services.app_settings_service import AppSettingsService


class AdminPayload(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None


class SettingsPayload(BaseModel):
    system_name: str
    bot_url: str
    support_line_1: str = ""
    support_line_2: str = ""
    timezone: str
    order_prefix: str
    api_docs_url: str = ""


class BootstrapPayload(BaseModel):
    admin: AdminPayload
    settings: SettingsPayload


def bootstrap_system(session: Session, payload: BootstrapPayload) -> dict[str, bool]:
    admin_service = AdminService(session)
    settings_service = AppSettingsService(session)

    try:
        admin_created = not admin_service.list_admins(include_inactive=True)
        settings_created = not settings_service.settings_exist()
        if admin_created:
            admin_service.create_admin(
                username=payload.admin.username,
                password_hash=get_password_hash(payload.admin.password),
                full_name=payload.admin.full_name.strip(),
                email=str(payload.admin.email) if payload.admin.email else None,
                role=AdminRole.ADMIN,
                commit=False,
            )
        if settings_created:
            settings_service.update_settings(
                **payload.settings.model_dump(),
                commit=False,
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"admin_created": admin_created, "settings_created": settings_created}


def main() -> int:
    try:
        payload = BootstrapPayload.model_validate(json.load(sys.stdin))
    except ValidationError as exc:
        print(
            "\n".join(
                ".".join(str(part) for part in error["loc"]) or "<root>"
                for error in exc.errors()
            ),
            file=sys.stderr,
        )
        return 1
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        print("invalid JSON", file=sys.stderr)
        return 1

    session: Session | None = None
    try:
        engine = create_engine_instance()
        init_database(engine)
        session = get_session_factory(engine)()
        result = bootstrap_system(session, payload)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(f"bootstrap failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
