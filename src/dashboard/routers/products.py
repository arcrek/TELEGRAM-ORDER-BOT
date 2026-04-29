"""
Products router.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.dashboard.auth import get_current_admin, get_db
from src.database.services.product_service import ProductService
from src.database.services.product_supplier_assignment_service import ProductSupplierAssignmentService
from src.database.models.enums import DeliveryType


router = APIRouter()


class ProductCreate(BaseModel):
    """Product creation schema."""
    id: str
    name: str
    description: Optional[str] = None
    delivery_type: DeliveryType = DeliveryType.PRE_UPLOADED
    upgrade_request_text: Optional[str] = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    """Product update schema."""
    name: Optional[str] = None
    description: Optional[str] = None
    delivery_type: Optional[DeliveryType] = None
    upgrade_request_text: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    """Product response schema."""
    id: str
    name: str
    description: Optional[str]
    delivery_type: str
    upgrade_request_text: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(15, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    only_active: Optional[bool] = Query(None, description="Filter by active status"),
    sort_by: Optional[str] = Query("name", description="Sort field: name, created_at"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc, desc"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    List products with pagination, search, filter, and sort.
    
    Args:
        page: Page number (1-indexed)
        per_page: Items per page
        search: Search term for name or description
        only_active: Filter by active status
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
    
    Returns:
        Paginated list of products
    """
    service = ProductService(db)
    
    # Get products with filters and sorting
    products = service.list_products(
        page=page,
        per_page=per_page,
        only_active=only_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    # Get total count with same filters
    total = service.get_total_count(only_active=only_active, search=search)
    
    return {
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "delivery_type": p.delivery_type.value,
                "upgrade_request_text": p.upgrade_request_text,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in products
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


@router.get("/{product_id}/suppliers")
async def get_product_suppliers(
    product_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all suppliers assigned to a product.
    
    Args:
        product_id: Product ID
    
    Returns:
        List of suppliers assigned to product
    """
    product_service = ProductService(db)
    assignment_service = ProductSupplierAssignmentService(db)
    
    # Verify product exists
    product = product_service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )
    
    suppliers = assignment_service.get_suppliers_by_product(product_id)
    
    return {"items": suppliers}


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get product by ID.
    
    Args:
        product_id: Product ID
    
    Returns:
        Product details
    """
    service = ProductService(db)
    product = service.get_product_by_id(product_id)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )
    
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "delivery_type": product.delivery_type.value,
        "upgrade_request_text": product.upgrade_request_text,
        "is_active": product.is_active,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new product.
    
    Args:
        product_data: Product creation data
    
    Returns:
        Created product
    """
    service = ProductService(db)
    
    # Check if product already exists
    existing = service.get_product_by_id(product_data.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with ID {product_data.id} already exists"
        )
    
    product = service.create_product({
        "id": product_data.id,
        "name": product_data.name,
        "description": product_data.description,
        "delivery_type": product_data.delivery_type,
        "upgrade_request_text": product_data.upgrade_request_text,
        "is_active": product_data.is_active,
    })

    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "delivery_type": product.delivery_type.value,
        "upgrade_request_text": product.upgrade_request_text,
        "is_active": product.is_active,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


@router.put("/{product_id}")
async def update_product(
    product_id: str,
    product_data: ProductUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update a product.
    
    Args:
        product_id: Product ID
        product_data: Product update data
    
    Returns:
        Updated product
    """
    service = ProductService(db)
    
    update_dict = {}
    if product_data.name is not None:
        update_dict["name"] = product_data.name
    if product_data.description is not None:
        update_dict["description"] = product_data.description
    if product_data.delivery_type is not None:
        update_dict["delivery_type"] = product_data.delivery_type
    if "upgrade_request_text" in product_data.model_fields_set:
        update_dict["upgrade_request_text"] = product_data.upgrade_request_text
    if product_data.is_active is not None:
        update_dict["is_active"] = product_data.is_active

    product = service.update_product(product_id, update_dict)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "delivery_type": product.delivery_type.value,
        "upgrade_request_text": product.upgrade_request_text,
        "is_active": product.is_active,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Permanently delete a product from the database.
    
    Args:
        product_id: Product ID
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If product not found or has related records
    """
    service = ProductService(db)
    
    success = service.delete_product(product_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )
    
    return {"message": f"Product {product_id} deleted successfully"}
