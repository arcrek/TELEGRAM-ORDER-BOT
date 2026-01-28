"""
Image of the Day (IOTD) router.
"""
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.services.iotd_settings_service import IotdSettingsService


router = APIRouter()


class IotdResponse(BaseModel):
    image_url: Optional[str] = None


class IotdUpdateRequest(BaseModel):
    # Allow null to clear. Use HttpUrl for basic validation when provided.
    image_url: Optional[HttpUrl] = None


@router.get("", response_model=IotdResponse, include_in_schema=True)
@router.get("/", response_model=IotdResponse, include_in_schema=False)
async def get_iotd(
    current_admin=Depends(require_viewer_or_admin),
    db: Session = Depends(get_db),
):
    service = IotdSettingsService(db)
    return IotdResponse(image_url=service.get_image_url())


@router.put("", response_model=IotdResponse, include_in_schema=True)
@router.put("/", response_model=IotdResponse, include_in_schema=False)
async def update_iotd(
    payload: IotdUpdateRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    service = IotdSettingsService(db)
    settings = service.set_image_url(str(payload.image_url) if payload.image_url else None)
    return IotdResponse(image_url=settings.image_url)

