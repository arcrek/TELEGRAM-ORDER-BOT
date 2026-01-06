"""
Script to create the first admin user for the dashboard.
Run this script to create an initial admin account.

Usage:
    python scripts/create_admin.py
    python scripts/create_admin.py --username admin --password admin123 --email admin@example.com
"""
import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.connection import get_session_factory, init_database, create_engine_instance
from src.database.services.admin_service import AdminService
from src.database.models.admin import AdminRole
from src.dashboard.auth import get_password_hash


def create_first_admin(username: str, password: str, full_name: str, email: str = None, role: AdminRole = AdminRole.ADMIN):
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
        print(f"   Password: {password}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin: {e}")
        return False
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description='Create the first admin user for the dashboard')
    parser.add_argument('--username', default='admin', help='Admin username (default: admin)')
    parser.add_argument('--password', default='admin123', help='Admin password (default: admin123)')
    parser.add_argument('--email', default=None, help='Admin email (optional)')
    parser.add_argument('--full-name', default='Administrator', help='Admin full name (default: Administrator)')
    parser.add_argument('--role', choices=['admin', 'viewer'], default='admin', help='Admin role (default: admin)')
    
    args = parser.parse_args()
    
    role = AdminRole.ADMIN if args.role == 'admin' else AdminRole.VIEWER
    
    print("🚀 Creating first admin user...")
    print(f"   Username: {args.username}")
    print(f"   Full Name: {args.full_name}")
    print(f"   Email: {args.email or 'N/A'}")
    print(f"   Role: {args.role}")
    print()
    
    success = create_first_admin(
        username=args.username,
        password=args.password,
        full_name=args.full_name,
        email=args.email,
        role=role,
    )
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()

