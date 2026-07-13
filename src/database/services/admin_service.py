"""
Admin service layer.
"""

import uuid
from typing import Optional
from sqlalchemy.orm import Session
from src.database.models.admin import Admin, AdminRole


class AdminService:
    """Service for admin operations."""

    def __init__(self, session: Session):
        """
        Initialize admin service.

        Args:
            session: Database session
        """
        self.session = session

    def generate_admin_id(self) -> str:
        """
        Generate a unique admin ID.

        Returns:
            Admin ID string
        """
        return f"admin_{uuid.uuid4().hex[:8]}"

    def get_admin_by_username(self, username: str) -> Optional[Admin]:
        """
        Get admin by username.

        Args:
            username: Admin username

        Returns:
            Admin instance or None if not found
        """
        return (
            self.session.query(Admin)
            .filter_by(username=username, is_active=True)
            .first()
        )

    def get_admin_by_id(self, admin_id: str) -> Optional[Admin]:
        """
        Get admin by ID.

        Args:
            admin_id: Admin ID

        Returns:
            Admin instance or None if not found
        """
        return self.session.query(Admin).filter_by(id=admin_id).first()

    def create_admin(
        self,
        username: str,
        password_hash: str,
        full_name: str,
        email: Optional[str] = None,
        role: AdminRole = AdminRole.VIEWER,
        commit: bool = True,
    ) -> Admin:
        """
        Create a new admin.

        Args:
            username: Admin username
            password_hash: Hashed password
            full_name: Admin full name
            email: Admin email (optional)
            role: Admin role (default: VIEWER)
            commit: Commit immediately; disable for caller-owned transactions

        Returns:
            Created Admin instance
        """
        admin = Admin(
            id=self.generate_admin_id(),
            username=username,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            is_active=True,
        )

        self.session.add(admin)
        if commit:
            self.session.commit()
            self.session.refresh(admin)
        else:
            self.session.flush()

        return admin

    def update_admin_status(self, admin_id: str, is_active: bool) -> Optional[Admin]:
        """
        Update admin active status.

        Args:
            admin_id: Admin ID
            is_active: New active status

        Returns:
            Updated Admin instance or None if not found
        """
        admin = self.get_admin_by_id(admin_id)
        if not admin:
            return None

        admin.is_active = is_active
        self.session.commit()
        self.session.refresh(admin)

        return admin

    def list_admins(self, include_inactive: bool = False) -> list[Admin]:
        """
        List all admins.

        Args:
            include_inactive: Whether to include inactive admins

        Returns:
            List of Admin instances
        """
        query = self.session.query(Admin)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.all()
