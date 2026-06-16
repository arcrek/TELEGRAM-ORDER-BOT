"""
Suppliers router.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.dashboard.auth import get_current_admin, get_db
from src.database.services.supplier_service import SupplierService
from src.database.services.product_supplier_assignment_service import ProductSupplierAssignmentService
from src.utils.datetime_format import to_utc_iso

router = APIRouter()


class SupplierStatusUpdate(BaseModel):
    """Supplier status update schema."""
    is_active: bool


class SupplierResponse(BaseModel):
    """Supplier response schema."""
    id: str
    telegram_user_id: int
    name: str
    is_active: bool
    created_at: str
    
    class Config:
        from_attributes = True


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_suppliers(
    only_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    List suppliers with optional filtering.
    
    Args:
        only_active: Filter by active status (None = all)
    
    Returns:
        List of suppliers
    """
    service = SupplierService(db)
    suppliers = service.list_suppliers(only_active=only_active)
    
    return {
        "items": [
            {
                "id": s.id,
                "telegram_user_id": s.telegram_user_id,
                "name": s.name,
                "is_active": s.is_active,
                "created_at": to_utc_iso(s.created_at),
            }
            for s in suppliers
        ]
    }


@router.get("/{supplier_id}")
async def get_supplier(
    supplier_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get supplier by ID.
    
    Args:
        supplier_id: Supplier ID
    
    Returns:
        Supplier details
    """
    service = SupplierService(db)
    supplier = service.get_supplier_by_id(supplier_id)
    
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found"
        )
    
    return {
        "id": supplier.id,
        "telegram_user_id": supplier.telegram_user_id,
        "name": supplier.name,
        "is_active": supplier.is_active,
        "created_at": to_utc_iso(supplier.created_at),
    }


@router.put("/{supplier_id}/status")
async def update_supplier_status(
    supplier_id: str,
    status_data: SupplierStatusUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update supplier active status.
    
    Args:
        supplier_id: Supplier ID
        status_data: Status update data
    
    Returns:
        Updated supplier
    """
    service = SupplierService(db)
    supplier = service.update_supplier_status(supplier_id, status_data.is_active)
    
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found"
        )
    
    return {
        "id": supplier.id,
        "telegram_user_id": supplier.telegram_user_id,
        "name": supplier.name,
        "is_active": supplier.is_active,
        "created_at": to_utc_iso(supplier.created_at),
    }


@router.get("/{supplier_id}/orders")
async def get_supplier_order_history(
    supplier_id: str,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of orders"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get order history for a supplier.
    
    Args:
        supplier_id: Supplier ID
        limit: Maximum number of orders to return
    
    Returns:
        List of supplier orders
    """
    service = SupplierService(db)
    
    # Verify supplier exists
    supplier = service.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found"
        )
    
    orders = service.get_supplier_order_history(supplier_id, limit=limit)
    
    return {"items": orders}


@router.get("/{supplier_id}/statistics")
async def get_supplier_statistics(
    supplier_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get performance statistics for a supplier.
    
    Args:
        supplier_id: Supplier ID
    
    Returns:
        Supplier statistics
    """
    service = SupplierService(db)
    
    # Verify supplier exists
    supplier = service.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found"
        )
    
    statistics = service.get_supplier_statistics(supplier_id)
    
    return statistics


@router.get("/{supplier_id}/products")
async def get_supplier_products(
    supplier_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all products assigned to a supplier.
    
    Args:
        supplier_id: Supplier ID
    
    Returns:
        List of products assigned to supplier
    """
    service = SupplierService(db)
    assignment_service = ProductSupplierAssignmentService(db)
    
    # Verify supplier exists
    supplier = service.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found"
        )
    
    products = assignment_service.get_products_by_supplier(supplier_id)
    
    return {"items": products}

