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
    system_name: str
    bot_url: str
    support_line_1: str
    support_line_2: str
    timezone: str
    order_prefix: str
    api_docs_url: str


class AppSettingsUpdateRequest(AppSettingsResponse):
    pass


class PublicAppSettingsResponse(BaseModel):
    system_name: str


def _response(settings) -> AppSettingsResponse:
    return AppSettingsResponse(
        system_name=settings.system_name,
        bot_url=settings.bot_url,
        support_line_1=settings.support_line_1,
        support_line_2=settings.support_line_2,
        timezone=settings.timezone,
        order_prefix=settings.order_prefix,
        api_docs_url=settings.api_docs_url,
    )


@router.get("/public", response_model=PublicAppSettingsResponse)
async def get_public_app_settings(db: Session = Depends(get_db)):
    settings = AppSettingsService(db).get_settings()
    return PublicAppSettingsResponse(system_name=settings.system_name)


@router.get("", response_model=AppSettingsResponse, include_in_schema=True)
@router.get("/", response_model=AppSettingsResponse, include_in_schema=False)
async def get_app_settings(
    current_admin=Depends(require_viewer_or_admin),
    db: Session = Depends(get_db),
):
    service = AppSettingsService(db)
    settings = service.get_settings()
    return _response(settings)


@router.put("", response_model=AppSettingsResponse, include_in_schema=True)
@router.put("/", response_model=AppSettingsResponse, include_in_schema=False)
async def update_app_settings(
    payload: AppSettingsUpdateRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    service = AppSettingsService(db)
    try:
        settings = service.update_settings(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _response(settings)
