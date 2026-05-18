"""
Variations router.
"""
import uuid
from typing import Optional, List, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, model_validator
from src.dashboard.auth import get_current_admin, get_db
from src.database.services.variation_service import VariationService
from src.database.services.product_service import ProductService


router = APIRouter()


class VariationCreate(BaseModel):
    """Variation creation schema."""
    id: Optional[str] = None
    product_id: str
    name: str
    price: int
    # stock is removed - it's calculated from pre-uploaded products
    is_active: bool = True


class VariationUpdate(BaseModel):
    """Variation update schema."""
    name: Optional[str] = None
    price: Optional[int] = None
    # stock is removed - it's calculated from pre-uploaded products
    is_active: Optional[bool] = None
    benefit_mode: Optional[str] = None  # 'bonus' | 'discount' | 'both'
    # Warning threshold for inventory aging/expiry tracking.
    # Both fields must be provided together or both must be null.
    warning_threshold_value: Optional[int] = None
    warning_threshold_unit: Optional[Literal['days', 'months', 'years']] = None

    @field_validator('warning_threshold_value')
    @classmethod
    def validate_threshold_value(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError('warning_threshold_value must be greater than 0')
        return v

    @model_validator(mode='after')
    def validate_threshold_pair(self) -> 'VariationUpdate':
        v = self.warning_threshold_value
        u = self.warning_threshold_unit
        if (v is None) != (u is None):
            raise ValueError(
                'warning_threshold_value and warning_threshold_unit must both be set or both be null'
            )
        return self


class VariationResponse(BaseModel):
    """Variation response schema."""
    id: str
    product_id: str
    product_name: Optional[str] = None
    name: str
    price: int
    stock: int
    is_active: bool
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class StockUpdate(BaseModel):
    """Stock update schema."""
    stock: int


class StockUpdateItem(BaseModel):
    """Single stock update item."""
    variation_id: str


class BulkStockUpdate(BaseModel):
    """Bulk stock update schema."""
    updates: List[StockUpdateItem]


class BulkVariationOperation(BaseModel):
    """Bulk variation operation schema."""
    variation_ids: List[str]


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_variations(
    product_id: Optional[str] = Query(None, description="Filter by product ID"),
    only_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    List variations grouped by product.
    
    Args:
        product_id: Optional product ID to filter by
        only_active: Optional filter for active variations only
    
    Returns:
        List of products with their variations
    """
    service = VariationService(db)
    items = service.list_all_variations_grouped(
        product_id=product_id,
        only_active=only_active,
    )
    
    return {"items": items}


@router.get("/low-stock")
async def get_low_stock_variations(
    threshold: int = Query(5, ge=0, description="Stock threshold"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get variations with stock below threshold, grouped by product.
    
    Args:
        threshold: Stock threshold (default: 5)
    
    Returns:
        List of products with low stock variations
    """
    service = VariationService(db)
    items = service.get_low_stock_variations(threshold=threshold)
    
    return {"items": items}


@router.get("/{variation_id}")
async def get_variation(
    variation_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get variation by ID.
    
    Args:
        variation_id: Variation ID
    
    Returns:
        Variation details
    """
    service = VariationService(db)
    variation = service.get_variation_by_id(variation_id)
    
    if not variation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variation {variation_id} not found"
        )
    
    # Get product name
    product_service = ProductService(db)
    product = product_service.get_product_by_id(variation.product_id)
    
    # Calculate stock from pre-uploaded products
    calculated_stock = service.calculate_stock_from_pre_uploaded(variation.id)
    
    return {
        "id": variation.id,
        "product_id": variation.product_id,
        "product_name": product.name if product else None,
        "name": variation.name,
        "price": variation.price,
        "stock": calculated_stock,
        "is_active": variation.is_active,
        "benefit_mode": getattr(variation, 'benefit_mode', 'bonus'),
        "created_at": variation.created_at.isoformat(),
        "updated_at": variation.updated_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_variation(
    variation_data: VariationCreate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new variation.
    
    Args:
        variation_data: Variation creation data
    
    Returns:
        Created variation
    """
    service = VariationService(db)

    variation_id = variation_data.id or str(uuid.uuid4())

    # Check if variation already exists
    existing = service.get_variation_by_id(variation_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Variation with ID {variation_id} already exists"
        )

    # Check if product exists
    product_service = ProductService(db)
    product = product_service.get_product_by_id(variation_data.product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {variation_data.product_id} not found"
        )

    variation = service.create_variation({
        "id": variation_id,
        "product_id": variation_data.product_id,
        "name": variation_data.name,
        "price": variation_data.price,
        "stock": 0,  # Stock is calculated from pre-uploaded products
        "is_active": variation_data.is_active,
    })
    
    # Calculate stock from pre-uploaded products
    calculated_stock = service.calculate_stock_from_pre_uploaded(variation.id)
    
    return {
        "id": variation.id,
        "product_id": variation.product_id,
        "product_name": product.name,
        "name": variation.name,
        "price": variation.price,
        "stock": calculated_stock,
        "is_active": variation.is_active,
        "benefit_mode": getattr(variation, 'benefit_mode', 'bonus'),
        "created_at": variation.created_at.isoformat(),
        "updated_at": variation.updated_at.isoformat(),
    }


@router.put("/{variation_id}")
async def update_variation(
    variation_id: str,
    variation_data: VariationUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update a variation.
    
    Args:
        variation_id: Variation ID
        variation_data: Variation update data
    
    Returns:
        Updated variation
    """
    service = VariationService(db)
    
    update_dict = {}
    if variation_data.name is not None:
        update_dict["name"] = variation_data.name
    if variation_data.price is not None:
        update_dict["price"] = variation_data.price
    # stock is not updated - it's calculated from pre-uploaded products
    if variation_data.is_active is not None:
        update_dict["is_active"] = variation_data.is_active
    if variation_data.benefit_mode is not None:
        if variation_data.benefit_mode not in ('bonus', 'discount', 'both'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="benefit_mode must be 'bonus', 'discount', or 'both'",
            )
        update_dict["benefit_mode"] = variation_data.benefit_mode
    # Threshold fields: include when explicitly provided in the request body.
    # model_validator guarantees they are both set or both null together.
    if variation_data.warning_threshold_value is not None or variation_data.warning_threshold_unit is not None:
        update_dict["warning_threshold_value"] = variation_data.warning_threshold_value
        update_dict["warning_threshold_unit"] = variation_data.warning_threshold_unit
    # Allow clearing the threshold by sending both as null (explicit nullification).
    # We detect this by checking the raw model fields: if either key appears in the
    # request body at all, the pair is included.  Pydantic sets them to None for nulls.
    elif 'warning_threshold_value' in variation_data.model_fields_set:
        update_dict["warning_threshold_value"] = None
        update_dict["warning_threshold_unit"] = None

    variation = service.update_variation(variation_id, update_dict)
    
    if not variation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variation {variation_id} not found"
        )
    
    # Get product name
    product_service = ProductService(db)
    product = product_service.get_product_by_id(variation.product_id)
    
    # Calculate stock from pre-uploaded products
    calculated_stock = service.calculate_stock_from_pre_uploaded(variation.id)
    
    return {
        "id": variation.id,
        "product_id": variation.product_id,
        "product_name": product.name if product else None,
        "name": variation.name,
        "price": variation.price,
        "stock": calculated_stock,
        "is_active": variation.is_active,
        "benefit_mode": getattr(variation, 'benefit_mode', 'bonus'),
        "created_at": variation.created_at.isoformat(),
        "updated_at": variation.updated_at.isoformat(),
    }


@router.put("/bulk/stock")
async def bulk_update_stock(
    bulk_data: BulkStockUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get stock for multiple variations (calculated from pre-uploaded products).
    Stock is automatically calculated from available pre-uploaded products.
    
    Args:
        bulk_data: Bulk stock query data (variation_ids are used to query stock)
    
    Returns:
        Summary with calculated stock values
    """
    service = VariationService(db)
    
    success_count = 0
    failed_count = 0
    errors = []
    results = []
    
    for update_item in bulk_data.updates:
        variation_id = update_item.variation_id
        
        variation = service.get_variation_by_id(variation_id)
        if variation:
            calculated_stock = service.calculate_stock_from_pre_uploaded(variation_id)
            results.append({
                "variation_id": variation_id,
                "stock": calculated_stock
            })
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"Variation {variation_id} not found")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "errors": errors,
        "results": results,
    }


@router.put("/{variation_id}/stock")
async def update_stock(
    variation_id: str,
    stock_data: StockUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get current stock for a variation (calculated from pre-uploaded products).
    Stock is automatically calculated from available pre-uploaded products.
    
    Args:
        variation_id: Variation ID
        stock_data: Stock data (ignored, stock is calculated automatically)
    
    Returns:
        Variation with calculated stock
    """
    service = VariationService(db)
    
    variation = service.get_variation_by_id(variation_id)
    
    if not variation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variation {variation_id} not found"
        )
    
    # Get product name
    product_service = ProductService(db)
    product = product_service.get_product_by_id(variation.product_id)
    
    # Calculate stock from pre-uploaded products
    calculated_stock = service.calculate_stock_from_pre_uploaded(variation.id)
    
    return {
        "id": variation.id,
        "product_id": variation.product_id,
        "product_name": product.name if product else None,
        "name": variation.name,
        "price": variation.price,
        "stock": calculated_stock,
        "is_active": variation.is_active,
        "benefit_mode": getattr(variation, 'benefit_mode', 'bonus'),
        "created_at": variation.created_at.isoformat(),
        "updated_at": variation.updated_at.isoformat(),
    }


@router.delete("/{variation_id}")
async def delete_variation(
    variation_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Permanently delete a variation from the database.
    
    Args:
        variation_id: Variation ID
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If variation not found or has related records
    """
    service = VariationService(db)
    
    success = service.delete_variation(variation_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variation {variation_id} not found"
        )
    
    return {"message": f"Variation {variation_id} deleted successfully"}


@router.put("/bulk/activate")
async def bulk_activate_variations(
    bulk_data: BulkVariationOperation,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Bulk activate variations.
    
    Args:
        bulk_data: Bulk operation data with variation IDs
    
    Returns:
        Summary with success/failure counts
    """
    service = VariationService(db)
    
    success_count = 0
    failed_count = 0
    errors = []
    
    for variation_id in bulk_data.variation_ids:
        variation = service.get_variation_by_id(variation_id)
        if variation:
            service.update_variation(variation_id, {"is_active": True})
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"Variation {variation_id} not found")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "errors": errors,
    }


@router.put("/bulk/deactivate")
async def bulk_deactivate_variations(
    bulk_data: BulkVariationOperation,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Bulk deactivate variations.
    
    Args:
        bulk_data: Bulk operation data with variation IDs
    
    Returns:
        Summary with success/failure counts
    """
    service = VariationService(db)
    
    success_count = 0
    failed_count = 0
    errors = []
    
    for variation_id in bulk_data.variation_ids:
        variation = service.get_variation_by_id(variation_id)
        if variation:
            service.update_variation(variation_id, {"is_active": False})
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"Variation {variation_id} not found")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "errors": errors,
    }


@router.post("/bulk/delete")
async def bulk_delete_variations(
    bulk_data: BulkVariationOperation,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Bulk delete variations.
    
    Args:
        bulk_data: Bulk operation data with variation IDs
    
    Returns:
        Summary with success/failure counts
    """
    service = VariationService(db)
    
    success_count = 0
    failed_count = 0
    errors = []
    
    for variation_id in bulk_data.variation_ids:
        success = service.delete_variation(variation_id)
        if success:
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"Variation {variation_id} not found")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "errors": errors,
    }

