"""
Bonus tiers router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.dashboard.auth import get_current_admin, get_db
from src.database.services.bonus_tier_service import BonusTierService
from src.utils.datetime_format import to_utc_iso

router = APIRouter()


class BonusTierCreate(BaseModel):
    """Bonus tier creation schema."""
    min_quantity: int = Field(..., ge=1, description="Minimum quantity to qualify for bonus")
    bonus_quantity: int = Field(..., ge=1, description="Number of free items")
    is_active: bool = True


class BonusTierUpdate(BaseModel):
    """Bonus tier update schema."""
    min_quantity: int | None = Field(None, ge=1, description="Minimum quantity to qualify for bonus")
    bonus_quantity: int | None = Field(None, ge=1, description="Number of free items")
    is_active: bool | None = None


class BonusTierResponse(BaseModel):
    """Bonus tier response schema."""
    id: str
    variation_id: str
    min_quantity: int
    bonus_quantity: int
    is_active: bool
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


@router.get("/variations/{variation_id}/bonus-tiers")
async def list_bonus_tiers(
    variation_id: str,
    only_active: bool = True,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    List all bonus tiers for a variation.
    
    Args:
        variation_id: Product variation ID
        only_active: If True, only return active tiers
    
    Returns:
        List of bonus tiers
    """
    service = BonusTierService(db)
    tiers = service.get_bonus_tiers_by_variation(variation_id, only_active=only_active)
    
    result = []
    for tier in tiers:
        result.append({
            "id": tier.id,
            "variation_id": tier.variation_id,
            "min_quantity": tier.min_quantity,
            "bonus_quantity": tier.bonus_quantity,
            "is_active": tier.is_active,
            "created_at": to_utc_iso(tier.created_at),
            "updated_at": to_utc_iso(tier.updated_at),
        })
    
    return {"items": result}


@router.post("/variations/{variation_id}/bonus-tiers", status_code=status.HTTP_201_CREATED)
async def create_bonus_tier(
    variation_id: str,
    data: BonusTierCreate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new bonus tier for a variation.
    
    Args:
        variation_id: Product variation ID
        data: Bonus tier data
    
    Returns:
        Created bonus tier
    """
    service = BonusTierService(db)
    
    try:
        tier = service.create_bonus_tier(
            variation_id=variation_id,
            min_quantity=data.min_quantity,
            bonus_quantity=data.bonus_quantity,
            is_active=data.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    return {
        "id": tier.id,
        "variation_id": tier.variation_id,
        "min_quantity": tier.min_quantity,
        "bonus_quantity": tier.bonus_quantity,
        "is_active": tier.is_active,
        "created_at": to_utc_iso(tier.created_at),
        "updated_at": to_utc_iso(tier.updated_at),
    }


@router.get("/bonus-tiers/{tier_id}")
async def get_bonus_tier(
    tier_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get a specific bonus tier.
    
    Args:
        tier_id: Bonus tier ID
    
    Returns:
        Bonus tier details
    """
    service = BonusTierService(db)
    tier = service.get_bonus_tier_by_id(tier_id)
    
    if not tier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bonus tier not found")
    
    return {
        "id": tier.id,
        "variation_id": tier.variation_id,
        "min_quantity": tier.min_quantity,
        "bonus_quantity": tier.bonus_quantity,
        "is_active": tier.is_active,
        "created_at": to_utc_iso(tier.created_at),
        "updated_at": to_utc_iso(tier.updated_at),
    }


@router.put("/bonus-tiers/{tier_id}")
async def update_bonus_tier(
    tier_id: str,
    data: BonusTierUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Update a bonus tier.
    
    Args:
        tier_id: Bonus tier ID
        data: Update data
    
    Returns:
        Updated bonus tier
    """
    service = BonusTierService(db)
    
    update_data = {}
    if data.min_quantity is not None:
        update_data['min_quantity'] = data.min_quantity
    if data.bonus_quantity is not None:
        update_data['bonus_quantity'] = data.bonus_quantity
    if data.is_active is not None:
        update_data['is_active'] = data.is_active
    
    try:
        tier = service.update_bonus_tier(tier_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    if not tier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bonus tier not found")
    
    return {
        "id": tier.id,
        "variation_id": tier.variation_id,
        "min_quantity": tier.min_quantity,
        "bonus_quantity": tier.bonus_quantity,
        "is_active": tier.is_active,
        "created_at": to_utc_iso(tier.created_at),
        "updated_at": to_utc_iso(tier.updated_at),
    }


@router.delete("/bonus-tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bonus_tier(
    tier_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a bonus tier.
    
    Args:
        tier_id: Bonus tier ID
    """
    service = BonusTierService(db)
    
    if not service.delete_bonus_tier(tier_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bonus tier not found")
    
