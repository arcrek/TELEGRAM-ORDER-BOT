"""
Bot UI settings router.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.services.bot_ui_settings_service import BotUiSettingsService

router = APIRouter()


class BotUiSettingsResponse(BaseModel):
    product_choose_text: str | None = None
    variation_choose_text: str | None = None
    upload_notification_header: str | None = None


class BotUiSettingsUpdateRequest(BaseModel):
    product_choose_text: str | None = None
    variation_choose_text: str | None = None
    upload_notification_header: str | None = None


@router.get("", response_model=BotUiSettingsResponse, include_in_schema=True)
@router.get("/", response_model=BotUiSettingsResponse, include_in_schema=False)
async def get_bot_ui_settings(
    current_admin=Depends(require_viewer_or_admin),
    db: Session = Depends(get_db),
):
    service = BotUiSettingsService(db)
    settings = service.get_settings()
    return BotUiSettingsResponse(
        product_choose_text=settings.product_choose_text,
        variation_choose_text=settings.variation_choose_text,
        upload_notification_header=settings.upload_notification_header,
    )


@router.put("", response_model=BotUiSettingsResponse, include_in_schema=True)
@router.put("/", response_model=BotUiSettingsResponse, include_in_schema=False)
async def update_bot_ui_settings(
    payload: BotUiSettingsUpdateRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    service = BotUiSettingsService(db)
    settings = service.update_settings(
        product_choose_text=payload.product_choose_text,
        variation_choose_text=payload.variation_choose_text,
        upload_notification_header=payload.upload_notification_header,
    )
    return BotUiSettingsResponse(
        product_choose_text=settings.product_choose_text,
        variation_choose_text=settings.variation_choose_text,
        upload_notification_header=settings.upload_notification_header,
    )
