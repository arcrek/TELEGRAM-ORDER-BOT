"""
Product supplier assignments router.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.dashboard.auth import get_current_admin, get_db
from src.database.services.product_supplier_assignment_service import ProductSupplierAssignmentService
from src.database.services.product_service import ProductService
from src.database.services.supplier_service import SupplierService
from src.utils.datetime_format import to_utc_iso

router = APIRouter()


class AssignmentCreate(BaseModel):
    """Assignment creation schema."""
    product_id: str
    supplier_id: str
    is_primary: bool = False


class AssignmentUpdate(BaseModel):
    """Assignment update schema."""
    product_id: str
    supplier_id: str
    is_primary: Optional[bool] = None


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(
    assignment_data: AssignmentCreate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a product-supplier assignment.
    
    Args:
        assignment_data: Assignment creation data
    
    Returns:
        Created assignment
    """
    assignment_service = ProductSupplierAssignmentService(db)
    
    assignment = assignment_service.create_assignment(
        product_id=assignment_data.product_id,
        supplier_id=assignment_data.supplier_id,
        is_primary=assignment_data.is_primary,
    )
    
    if not assignment:
        # Check if product/supplier exists or if assignment already exists
        product_service = ProductService(db)
        supplier_service = SupplierService(db)
        
        product = product_service.get_product_by_id(assignment_data.product_id)
        supplier = supplier_service.get_supplier_by_id(assignment_data.supplier_id)
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {assignment_data.product_id} not found"
            )
        
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier {assignment_data.supplier_id} not found"
            )
        
        # If both exist, assignment already exists
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment already exists for this product and supplier"
        )
    
    return {
        "id": assignment.id,
        "product_id": assignment.product_id,
        "supplier_id": assignment.supplier_id,
        "is_primary": assignment.is_primary,
        "created_at": to_utc_iso(assignment.created_at),
    }


@router.put("/assignments")
async def update_assignment(
    update_data: AssignmentUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update an assignment.
    
    Args:
        update_data: Update data with product_id, supplier_id, and is_primary
    
    Returns:
        Updated assignment
    """
    assignment_service = ProductSupplierAssignmentService(db)
    
    assignment = assignment_service.update_assignment(
        product_id=update_data.product_id,
        supplier_id=update_data.supplier_id,
        is_primary=update_data.is_primary,
    )
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    return {
        "id": assignment.id,
        "product_id": assignment.product_id,
        "supplier_id": assignment.supplier_id,
        "is_primary": assignment.is_primary,
        "created_at": to_utc_iso(assignment.created_at),
    }


@router.delete("/assignments")
async def delete_assignment(
    product_id: str = Query(..., description="Product ID"),
    supplier_id: str = Query(..., description="Supplier ID"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Delete an assignment.
    
    Args:
        product_id: Product ID
        supplier_id: Supplier ID
    
    Returns:
        Success message
    """
    assignment_service = ProductSupplierAssignmentService(db)
    
    success = assignment_service.delete_assignment(
        product_id=product_id,
        supplier_id=supplier_id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    return {"message": "Assignment deleted successfully"}

