"""
Authentication and authorization for dashboard.
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.database.connection import get_db_session
from src.database.models.admin import Admin, AdminRole

get_db = get_db_session  # shared singleton-backed session factory

# Password hashing - use bcrypt directly to avoid passlib backend detection issues

# JWT settings
SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 1 day (24 hours * 60 minutes)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def _require_secret_key() -> str:
    """Return the JWT secret, raising a clear error if it is not configured.

    Read lazily (not at import) so tests and runtime can set the env var
    before the first auth operation.
    """
    key = os.getenv("DASHBOARD_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "DASHBOARD_SECRET_KEY environment variable must be set "
            "(JWT signing key). Refusing to sign or verify tokens without it."
        )
    return key


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        True if password matches, False otherwise
    """
    # Truncate password to 72 bytes for bcrypt
    password_bytes = plain_password.encode('utf-8')[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """
    Hash a password.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    # Bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def get_admin_by_username(session: Session, username: str) -> Admin | None:
    """
    Get admin by username.
    
    Args:
        session: Database session
        username: Admin username
        
    Returns:
        Admin instance or None
    """
    return session.query(Admin).filter_by(username=username, is_active=True).first()


def authenticate_admin(session: Session, username: str, password: str) -> Admin | None:
    """
    Authenticate an admin.
    
    Args:
        session: Database session
        username: Admin username
        password: Plain text password
        
    Returns:
        Admin instance if authenticated, None otherwise
    """
    admin = get_admin_by_username(session, username)
    if not admin:
        return None
    try:
        if not verify_password(password, admin.password_hash):
            return None
    # passlib can fail in more ways than ValueError depending on backend/hash
    # format; any failure here must fall back to raw bcrypt rather than 500
    # a login request.
    except Exception:  # noqa: BLE001
        # Fallback to direct bcrypt if passlib fails
        import bcrypt
        try:
            if not bcrypt.checkpw(password.encode('utf-8'), admin.password_hash.encode('utf-8')):
                return None
        # Same reasoning: a broken hash/backend must deny auth, not crash it.
        except Exception:  # noqa: BLE001
            return None
    return admin


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in token
        expires_delta: Optional expiration delta
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, _require_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """
    Get current authenticated admin from JWT token.
    
    Args:
        token: JWT token
        session_factory: Database session factory
        
    Returns:
        Admin instance
        
    Raises:
        HTTPException: If token is invalid or admin not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, _require_secret_key(), algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    admin = get_admin_by_username(db, username)
    if admin is None:
        raise credentials_exception
    return admin


def require_admin_role(current_admin: Admin = Depends(get_current_admin)) -> Admin:
    """
    Require admin role (full access).
    
    Args:
        current_admin: Current authenticated admin
        
    Returns:
        Admin instance
        
    Raises:
        HTTPException: If admin doesn't have admin role
    """
    if current_admin.role != AdminRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_admin


def require_viewer_or_admin(current_admin: Admin = Depends(get_current_admin)) -> Admin:
    """
    Require viewer or admin role (any authenticated user).
    
    Args:
        current_admin: Current authenticated admin
        
    Returns:
        Admin instance
    """
    return current_admin

