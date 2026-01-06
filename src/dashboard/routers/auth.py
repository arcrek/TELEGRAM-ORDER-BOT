"""
Authentication router.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from src.database.models.admin import Admin, AdminRole
from src.dashboard.auth import (
    authenticate_admin,
    create_access_token,
    get_password_hash,
    get_admin_by_username,
    get_current_admin,
    require_admin_role,
    get_db,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter()


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"


class AdminCreate(BaseModel):
    """Admin creation model."""

    username: str
    email: EmailStr | None = None
    password: str
    full_name: str
    role: AdminRole = AdminRole.VIEWER


class AdminResponse(BaseModel):
    """Admin response model."""

    id: str
    username: str
    email: str | None
    full_name: str
    role: AdminRole
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login endpoint.
    
    Args:
        form_data: OAuth2 password form data
        session_factory: Database session factory
        
    Returns:
        Access token
    """
    admin = authenticate_admin(db, form_data.username, form_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    from datetime import datetime, timezone
    admin.last_login = datetime.now(timezone.utc)
    db.commit()
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": admin.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=AdminResponse)
async def get_current_user_info(current_admin: Admin = Depends(get_current_admin)):
    """
    Get current user information.
    
    Args:
        current_admin: Current authenticated admin
        
    Returns:
        Admin information
    """
    return AdminResponse(
        id=current_admin.id,
        username=current_admin.username,
        email=current_admin.email,
        full_name=current_admin.full_name,
        role=current_admin.role,
        is_active=current_admin.is_active,
        created_at=current_admin.created_at.isoformat(),
    )


@router.post("/register", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def register(
    admin_data: AdminCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_admin_role),
):
    """
    Register a new admin (admin only).
    
    Args:
        admin_data: Admin creation data
        session_factory: Database session factory
        current_admin: Current authenticated admin (must be admin role)
        
    Returns:
        Created admin
    """
    # Check if username already exists
    existing = get_admin_by_username(db, admin_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    
    # Create admin
    import uuid
    admin = Admin(
        id=f"admin_{uuid.uuid4().hex[:8]}",
        username=admin_data.username,
        email=admin_data.email,
        password_hash=get_password_hash(admin_data.password),
        full_name=admin_data.full_name,
        role=admin_data.role,
        is_active=True,
    )
    
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    return AdminResponse(
        id=admin.id,
        username=admin.username,
        email=admin.email,
        full_name=admin.full_name,
        role=admin.role,
        is_active=admin.is_active,
        created_at=admin.created_at.isoformat(),
    )

