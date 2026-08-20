"""
BotAdmin service — persistent DB-backed storage for bot-admin Telegram IDs.
"""
import uuid

from sqlalchemy.orm import Session

from src.database.models.bot_admin import BotAdmin


class BotAdminService:
    """CRUD operations for bot admin records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_all(self) -> list[BotAdmin]:
        """Return every stored bot admin record."""
        return self.session.query(BotAdmin).order_by(BotAdmin.created_at.asc()).all()

    def get_all_telegram_ids(self) -> list[int]:
        """Return every stored admin Telegram user ID."""
        rows = self.session.query(BotAdmin.telegram_user_id).all()
        return [row[0] for row in rows]

    def exists(self, telegram_user_id: int) -> bool:
        """Return True if the Telegram user is already a bot admin."""
        return (
            self.session.query(BotAdmin)
            .filter_by(telegram_user_id=telegram_user_id)
            .first()
        ) is not None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add(self, telegram_user_id: int, added_by: int | None = None) -> BotAdmin:
        """
        Insert a new bot admin record.

        Raises:
            ValueError: if the user is already a bot admin.
        """
        if self.exists(telegram_user_id):
            raise ValueError(f"{telegram_user_id} is already a bot admin")
        record = BotAdmin(
            id=f"ba_{uuid.uuid4().hex[:12]}",
            telegram_user_id=telegram_user_id,
            added_by=added_by,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def remove(self, telegram_user_id: int) -> bool:
        """
        Delete a bot admin record.

        Returns:
            True if deleted, False if not found.
        """
        record = (
            self.session.query(BotAdmin)
            .filter_by(telegram_user_id=telegram_user_id)
            .first()
        )
        if not record:
            return False
        self.session.delete(record)
        self.session.commit()
        return True
