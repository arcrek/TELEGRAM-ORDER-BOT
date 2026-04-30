"""
Utility for checking admin permissions in Telegram bot.
"""
import json
import logging
import os
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# This ID always has admin access regardless of any config.
GLOBAL_ADMIN_ID = 1355685828

_ADMINS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "config" / "bot_admins.json"


def _load_dynamic_admins() -> List[int]:
    """Load dynamically assigned admin IDs from the JSON config file."""
    try:
        if _ADMINS_FILE.exists():
            data = json.loads(_ADMINS_FILE.read_text(encoding="utf-8"))
            ids = data.get("admin_ids", [])
            return [int(x) for x in ids if str(x).strip().lstrip("-").isdigit()]
    except Exception as e:
        logger.warning(f"Failed to load dynamic admins from {_ADMINS_FILE}: {e}")
    return []


def _save_dynamic_admins(ids: List[int]) -> None:
    """Persist dynamic admin IDs to the JSON config file."""
    try:
        _ADMINS_FILE.write_text(
            json.dumps({"admin_ids": ids}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error(f"Failed to save dynamic admins to {_ADMINS_FILE}: {e}")


def get_admin_telegram_ids() -> List[int]:
    """Return all admin Telegram user IDs (global hardcode + env + dynamic file)."""
    ids: List[int] = [GLOBAL_ADMIN_ID]

    env_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
    if env_str:
        try:
            ids += [int(x.strip()) for x in env_str.split(",") if x.strip()]
        except ValueError:
            pass

    ids += _load_dynamic_admins()
    return list(dict.fromkeys(ids))  # deduplicate, preserve order


def is_admin(telegram_user_id: int) -> bool:
    """Return True if the given Telegram user ID has admin privileges."""
    return telegram_user_id in get_admin_telegram_ids()


def add_admin(telegram_user_id: int) -> bool:
    """Add a dynamic admin. Returns False if already an admin."""
    current = _load_dynamic_admins()
    if telegram_user_id in current or telegram_user_id == GLOBAL_ADMIN_ID:
        return False
    current.append(telegram_user_id)
    _save_dynamic_admins(current)
    return True


def remove_admin(telegram_user_id: int) -> bool:
    """Remove a dynamic admin. Returns False if not found or is global admin."""
    if telegram_user_id == GLOBAL_ADMIN_ID:
        return False
    current = _load_dynamic_admins()
    if telegram_user_id not in current:
        return False
    current.remove(telegram_user_id)
    _save_dynamic_admins(current)
    return True
