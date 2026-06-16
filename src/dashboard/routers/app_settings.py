"""
App settings router — global application configuration (timezone etc.).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.services.app_settings_service import AppSettingsService


router = APIRouter()


class AppSettingsResponse(BaseModel):
    timezone: str


class AppSettingsUpdateRequest(BaseModel):
    timezone: str


@router.get("", response_model=AppSettingsResponse, include_in_schema=True)
@router.get("/", response_model=AppSettingsResponse, include_in_schema=False)
async def get_app_settings(
    current_admin=Depends(require_viewer_or_admin),
    db: Session = Depends(get_db),
):
    service = AppSettingsService(db)
    settings = service.get_settings()
    return AppSettingsResponse(timezone=settings.timezone)


@router.put("", response_model=AppSettingsResponse, include_in_schema=True)
@router.put("/", response_model=AppSettingsResponse, include_in_schema=False)
async def update_app_settings(
    payload: AppSettingsUpdateRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    service = AppSettingsService(db)
    try:
        settings = service.update_settings(timezone=payload.timezone)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return AppSettingsResponse(timezone=settings.timezone)
