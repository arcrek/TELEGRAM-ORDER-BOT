"""
Discount tiers router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.dashboard.auth import get_current_admin, get_db, require_admin_role
from src.database.services.discount_tier_service import DiscountTierService
from src.utils.datetime_format import to_utc_iso

router = APIRouter()


class DiscountTierCreate(BaseModel):
    min_quantity: int = Field(..., ge=1)
    discount_type: str = Field(..., description="'percentage' or 'fixed_price'")
    discount_value: int = Field(..., ge=1)
    is_active: bool = True


class DiscountTierUpdate(BaseModel):
    min_quantity: int | None = Field(None, ge=1)
    discount_type: str | None = None
    discount_value: int | None = Field(None, ge=1)
    is_active: bool | None = None


def _tier_dict(tier) -> dict:
    return {
        "id": tier.id,
        "variation_id": tier.variation_id,
        "min_quantity": tier.min_quantity,
        "discount_type": tier.discount_type,
        "discount_value": tier.discount_value,
        "is_active": tier.is_active,
        "created_at": to_utc_iso(tier.created_at),
        "updated_at": to_utc_iso(tier.updated_at),
    }


@router.get("/variations/{variation_id}/discount-tiers")
async def list_discount_tiers(
    variation_id: str,
    only_active: bool = True,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = DiscountTierService(db)
    tiers = service.get_discount_tiers_by_variation(variation_id, only_active=only_active)
    return {"items": [_tier_dict(t) for t in tiers]}


@router.post("/variations/{variation_id}/discount-tiers", status_code=status.HTTP_201_CREATED)
async def create_discount_tier(
    variation_id: str,
    data: DiscountTierCreate,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    service = DiscountTierService(db)
    try:
        tier = service.create_discount_tier(
            variation_id=variation_id,
            min_quantity=data.min_quantity,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            is_active=data.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _tier_dict(tier)


@router.get("/discount-tiers/{tier_id}")
async def get_discount_tier(
    tier_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = DiscountTierService(db)
    tier = service.get_discount_tier_by_id(tier_id)
    if not tier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount tier not found")
    return _tier_dict(tier)


@router.put("/discount-tiers/{tier_id}")
async def update_discount_tier(
    tier_id: str,
    data: DiscountTierUpdate,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    service = DiscountTierService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    try:
        tier = service.update_discount_tier(tier_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not tier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount tier not found")
    return _tier_dict(tier)


@router.delete("/discount-tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discount_tier(
    tier_id: str,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    service = DiscountTierService(db)
    if not service.delete_discount_tier(tier_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount tier not found")
