"""
API authentication dependency for the public Order-via-API endpoints.

Parses `Authorization: Bearer <token>`, resolves the BotUser by token,
and raises HTTP 401 if the token is missing, malformed, or invalid.
"""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db
from src.database.models.bot_user import BotUser
from src.database.services.bot_user_service import BotUserService


async def get_api_user(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
) -> BotUser:
    """
    FastAPI dependency: validate Bearer token and return the owning BotUser.

    Raises:
        HTTPException 401: if the header is missing, not a Bearer token,
                           or the token is unknown / belongs to an inactive user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not authorization.startswith("Bearer "):
        raise credentials_exception

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise credentials_exception

    user = BotUserService(db).get_user_by_api_token(token)
    if user is None:
        raise credentials_exception

    return user
