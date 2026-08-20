"""Block service — manage the blocklist and check whether a user is blocked."""


from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from src.database.models.blocked_users import BlockedUser


class BlockService:
    """Service for blocking/unblocking users and checking block status."""

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def parse_identifier(identifier: str) -> tuple[int | None, str | None]:
        """Parse a raw identifier into (telegram_user_id, username).

        All-digits (optionally signed) → numeric id; otherwise a username
        (leading '@' stripped, lowercased). Raises ValueError if empty.
        """
        raw = (identifier or "").strip()
        if not raw:
            raise ValueError("Empty identifier")
        is_username = raw.startswith("@") or not raw.lstrip("-").lstrip("+").isdigit()
        if is_username:
            return None, raw.lstrip("@").lower()
        return int(raw), None

    def is_blocked(
        self, telegram_user_id: int | None, username: str | None
    ) -> bool:
        """True if the id OR the (case-insensitive) username is blocked."""
        conditions = []
        if telegram_user_id is not None:
            conditions.append(BlockedUser.telegram_user_id == telegram_user_id)
        if username:
            conditions.append(
                func.lower(BlockedUser.username) == username.lstrip("@").lower()
            )
        if not conditions:
            return False
        return (
            self.session.query(BlockedUser.id).filter(or_(*conditions)).first()
            is not None
        )

    def add_block(
        self,
        *,
        telegram_user_id: int | None = None,
        username: str | None = None,
    ) -> BlockedUser:
        """Create a block row (idempotent). Raises ValueError if no identifier."""
        if telegram_user_id is None and not username:
            raise ValueError("Must provide telegram_user_id or username")
        username_norm = username.lstrip("@").lower() if username else None

        existing = self.session.query(BlockedUser)
        if telegram_user_id is not None:
            existing = existing.filter(BlockedUser.telegram_user_id == telegram_user_id)
        else:
            existing = existing.filter(
                func.lower(BlockedUser.username) == username_norm
            )
        found = existing.first()
        if found:
            return found

        row = BlockedUser(telegram_user_id=telegram_user_id, username=username_norm)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def block(self, identifier: str) -> BlockedUser:
        """Parse a raw identifier and block it (idempotent)."""
        tid, uname = self.parse_identifier(identifier)
        return self.add_block(telegram_user_id=tid, username=uname)

    def remove_block(self, block_id: int) -> bool:
        """Remove a block by primary key. True if a row was deleted."""
        row = self.session.query(BlockedUser).filter_by(id=block_id).first()
        if not row:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def unblock(self, identifier: str) -> bool:
        """Parse a raw identifier and remove the matching block. True if removed."""
        tid, uname = self.parse_identifier(identifier)
        query = self.session.query(BlockedUser)
        if tid is not None:
            query = query.filter(BlockedUser.telegram_user_id == tid)
        else:
            query = query.filter(func.lower(BlockedUser.username) == uname)
        row = query.first()
        if not row:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def list_blocked(
        self,
        search: str | None = None,
        page: int = 1,
        per_page: int = 15,
    ) -> tuple[list[BlockedUser], int]:
        """Paginated list of block rows, newest first, optional substring search."""
        query = self.session.query(BlockedUser)
        if search:
            term = f"%{search.strip().lstrip('@').lower()}%"
            query = query.filter(
                or_(
                    func.lower(BlockedUser.username).like(term),
                    cast(BlockedUser.telegram_user_id, String).like(term),
                )
            )
        total = query.count()
        items = (
            query.order_by(BlockedUser.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total
