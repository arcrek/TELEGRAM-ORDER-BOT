"""
Utility for checking bot-admin permissions.

Admin IDs are stored in the `bot_admins` database table (persists across
Docker rebuilds). The configured bot owner is always granted access and is
the only identity that can add/remove other admins via /setadmin.
"""
import logging
import os

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

def _get_session():
    """Open and return a fresh synchronous DB session."""
    from src.database.connection import get_session_factory
    return get_session_factory()()


# ---------------------------------------------------------------------------
# Public read helpers
# ---------------------------------------------------------------------------


def get_owner_telegram_id() -> int | None:
    """Return the configured bot owner, failing closed on invalid input."""
    raw = os.getenv("BOT_OWNER_TELEGRAM_ID", "").strip()
    try:
        owner_id = int(raw)
    except ValueError:
        logger.error("BOT_OWNER_TELEGRAM_ID must be a positive integer")
        return None
    if owner_id <= 0:
        logger.error("BOT_OWNER_TELEGRAM_ID must be a positive integer")
        return None
    return owner_id


def _database_admin_ids() -> list[int]:
    session = _get_session()
    try:
        from src.database.services.bot_admin_service import BotAdminService

        return BotAdminService(session).get_all_telegram_ids()
    except SQLAlchemyError as exc:
        logger.warning("Failed to load bot admins from DB: %s", exc)
        return []
    finally:
        session.close()


def get_admin_telegram_ids() -> list[int]:
    """Return the configured owner and database-backed admins."""
    owner_id = get_owner_telegram_id()
    values = ([owner_id] if owner_id is not None else []) + _database_admin_ids()
    return list(dict.fromkeys(values))


def is_owner(telegram_user_id: int) -> bool:
    """Return whether the Telegram user is the configured bot owner."""
    return telegram_user_id == get_owner_telegram_id()


def is_admin(telegram_user_id: int) -> bool:
    """Return True if the given Telegram user ID has bot-admin privileges."""
    return telegram_user_id in get_admin_telegram_ids()


# ---------------------------------------------------------------------------
# Mutations (called from /setadmin — sync context, super admin only)
# ---------------------------------------------------------------------------


def add_admin(telegram_user_id: int, added_by: int | None = None) -> bool:
    """
    Add a bot admin to the DB.

    Returns True on success, False if the user is already an admin or
    the write fails.
    """
    if telegram_user_id in get_admin_telegram_ids():
        return False  # already an admin from any source

    session = _get_session()
    try:
        from src.database.services.bot_admin_service import BotAdminService
        BotAdminService(session).add(telegram_user_id, added_by=added_by)
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to add bot admin {telegram_user_id} to DB: {e}")
        return False
    finally:
        session.close()


def remove_admin(telegram_user_id: int) -> bool:
    """
    Remove a bot admin from the DB.

    Returns True on success, False if the user was not found or is the owner.
    """
    if is_owner(telegram_user_id):
        return False

    session = _get_session()
    try:
        from src.database.services.bot_admin_service import BotAdminService
        return BotAdminService(session).remove(telegram_user_id)
    except SQLAlchemyError as e:
        logger.error(f"Failed to remove bot admin {telegram_user_id} from DB: {e}")
        return False
    finally:
        session.close()
