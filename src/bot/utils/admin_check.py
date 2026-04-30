"""
Utility for checking bot-admin permissions.

Admin IDs are stored in the `bot_admins` database table (persists across
Docker rebuilds). The GLOBAL_ADMIN_ID is always granted access regardless
of the database contents, and is the only identity that can add/remove
other admins via /setadmin.
"""
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

# This ID always has admin access regardless of any config or DB state.
GLOBAL_ADMIN_ID = 1355685828


def _get_session():
    """Open and return a fresh synchronous DB session."""
    from src.database.connection import get_session_factory
    return get_session_factory()()


# ---------------------------------------------------------------------------
# Public read helpers
# ---------------------------------------------------------------------------


def get_admin_telegram_ids() -> List[int]:
    """
    Return all admin Telegram user IDs.

    Sources (in order, deduplicated):
      1. GLOBAL_ADMIN_ID (hardcoded super admin)
      2. ADMIN_TELEGRAM_IDS env var (comma-separated)
      3. bot_admins DB table
    """
    ids: List[int] = [GLOBAL_ADMIN_ID]

    env_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
    if env_str:
        for part in env_str.split(","):
            part = part.strip()
            if part:
                try:
                    ids.append(int(part))
                except ValueError:
                    pass

    session = _get_session()
    try:
        from src.database.services.bot_admin_service import BotAdminService
        ids += BotAdminService(session).get_all_telegram_ids()
    except Exception as e:
        logger.warning(f"Failed to load bot admins from DB: {e}")
    finally:
        session.close()

    return list(dict.fromkeys(ids))  # deduplicate, preserve order


def is_admin(telegram_user_id: int) -> bool:
    """Return True if the given Telegram user ID has bot-admin privileges."""
    return telegram_user_id in get_admin_telegram_ids()


# ---------------------------------------------------------------------------
# Mutations (called from /setadmin — sync context, super admin only)
# ---------------------------------------------------------------------------


def add_admin(telegram_user_id: int, added_by: Optional[int] = None) -> bool:
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
    except Exception as e:
        logger.error(f"Failed to add bot admin {telegram_user_id} to DB: {e}")
        return False
    finally:
        session.close()


def remove_admin(telegram_user_id: int) -> bool:
    """
    Remove a bot admin from the DB.

    Returns True on success, False if the user was not found or is the
    GLOBAL_ADMIN_ID (cannot be removed).
    """
    if telegram_user_id == GLOBAL_ADMIN_ID:
        return False

    session = _get_session()
    try:
        from src.database.services.bot_admin_service import BotAdminService
        return BotAdminService(session).remove(telegram_user_id)
    except Exception as e:
        logger.error(f"Failed to remove bot admin {telegram_user_id} from DB: {e}")
        return False
    finally:
        session.close()
