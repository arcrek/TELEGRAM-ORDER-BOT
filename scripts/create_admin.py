"""
Script to create the first admin user for the dashboard.
Run this script to create an initial admin account.

Usage:
    python scripts/create_admin.py --username admin --full-name Administrator
"""

import argparse
import getpass
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.connection import (
    get_session_factory,
    init_database,
    create_engine_instance,
)
from src.database.services.admin_service import AdminService
from src.database.models.admin import AdminRole
from src.dashboard.auth import get_password_hash


def create_first_admin(
    username: str,
    password: str,
    full_name: str,
    email: str | None = None,
    role: AdminRole = AdminRole.ADMIN,
) -> bool:
    """Create the first admin user."""
    # Initialize database
    engine = create_engine_instance()
    init_database(engine)

    # Get session
    session_factory = get_session_factory(engine)
    session = session_factory()

    try:
        admin_service = AdminService(session)

        # Check if admin already exists
        existing = admin_service.get_admin_by_username(username)
        if existing:
            print(f"❌ Admin with username '{username}' already exists!")
            return False

        # Hash password
        password_hash = get_password_hash(password)

        # Create admin
        admin = admin_service.create_admin(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            email=email,
            role=role,
        )

        print("✅ Admin created successfully!")
        print(f"   Username: {admin.username}")
        print(f"   Full Name: {admin.full_name}")
        print(f"   Email: {admin.email or 'N/A'}")
        print(f"   Role: {admin.role.value}")
        print(f"   ID: {admin.id}")
        print("\n📝 You can now login to the dashboard with:")
        print(f"   Username: {username}")

        return True

    except Exception as e:
        print(f"❌ Error creating admin: {type(e).__name__}")
        return False
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the first admin user for the dashboard"
    )
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--email", default=None, help="Admin email (optional)")
    parser.add_argument("--full-name", required=True, help="Admin full name")
    parser.add_argument(
        "--role",
        choices=["admin", "viewer"],
        default="admin",
        help="Admin role (default: admin)",
    )
    password_group = parser.add_mutually_exclusive_group()
    password_group.add_argument("--password-stdin", action="store_true")

    args = parser.parse_args()

    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            parser.error("passwords do not match")
    if len(password) < 12:
        parser.error("password must contain at least 12 characters")

    role = AdminRole.ADMIN if args.role == "admin" else AdminRole.VIEWER

    print("🚀 Creating first admin user...")
    print(f"   Username: {args.username}")
    print(f"   Full Name: {args.full_name}")
    print(f"   Email: {args.email or 'N/A'}")
    print(f"   Role: {args.role}")
    print()

    success = create_first_admin(
        username=args.username,
        password=password,
        full_name=args.full_name,
        email=args.email,
        role=role,
    )

    if not success:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
