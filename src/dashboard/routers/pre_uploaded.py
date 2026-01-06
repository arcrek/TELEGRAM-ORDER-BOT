"""
Pre-uploaded product management router.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.dashboard.auth import get_current_admin, get_db
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.services.pre_uploaded_service import PreUploadedService


router = APIRouter()


class PreUploadedProductResponse(BaseModel):
    """Pre-uploaded product response schema."""
    id: str
    product_id: str
    product_name: str
    variation_id: str
    variation_name: str
    product_data: str
    is_used: bool
    used_at: Optional[str]
    used_by_order_id: Optional[str]
    created_at: str
    
    class Config:
        from_attributes = True


@router.get("/pre-uploaded-products")
async def list_pre_uploaded_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    product_id: Optional[str] = Query(None),
    variation_id: Optional[str] = Query(None),
    is_used: Optional[bool] = Query(None),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    List pre-uploaded products with filters.
    
    Args:
        page: Page number
        per_page: Items per page
        product_id: Filter by product ID
        variation_id: Filter by variation ID
        is_used: Filter by used status
    
    Returns:
        Paginated list of pre-uploaded products
    """
    query = db.query(PreUploadedProduct)
    
    if product_id:
        query = query.filter_by(product_id=product_id)
    if variation_id:
        query = query.filter_by(variation_id=variation_id)
    if is_used is not None:
        query = query.filter_by(is_used=is_used)
    
    total = query.count()
    offset = (page - 1) * per_page
    products = query.offset(offset).limit(per_page).all()
    
    # Enrich with product and variation names
    result = []
    for p in products:
        product = db.query(Product).filter_by(id=p.product_id).first()
        variation = db.query(ProductVariation).filter_by(id=p.variation_id).first()
        
        result.append({
            "id": p.id,
            "product_id": p.product_id,
            "product_name": product.name if product else "Unknown",
            "variation_id": p.variation_id,
            "variation_name": variation.name if variation else "Unknown",
            "product_data": p.product_data,
            "is_used": p.is_used,
            "used_at": p.used_at.isoformat() if p.used_at else None,
            "used_by_order_id": p.used_by_order_id,
            "created_at": p.created_at.isoformat(),
        })
    
    return {
        "items": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


@router.get("/pre-uploaded-products/statistics")
async def get_pre_uploaded_statistics(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get pre-uploaded product statistics.
    
    Returns:
        Statistics dictionary
    """
    total = db.query(PreUploadedProduct).count()
    used = db.query(PreUploadedProduct).filter_by(is_used=True).count()
    available = db.query(PreUploadedProduct).filter_by(is_used=False).count()
    
    # Group by product
    products = db.query(Product).all()
    by_product = {}
    for product in products:
        count = db.query(PreUploadedProduct).filter_by(product_id=product.id).count()
        if count > 0:
            by_product[product.id] = {
                "product_id": product.id,
                "product_name": product.name,
                "total": count,
                "used": db.query(PreUploadedProduct).filter_by(product_id=product.id, is_used=True).count(),
                "available": db.query(PreUploadedProduct).filter_by(product_id=product.id, is_used=False).count(),
            }
    
    return {
        "total": total,
        "used": used,
        "available": available,
        "by_product": by_product,
    }


@router.put("/pre-uploaded-products/{product_id}/mark-used")
async def mark_product_as_used(
    product_id: str,
    order_id: Optional[str] = None,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Mark a pre-uploaded product as used.
    
    Args:
        product_id: Pre-uploaded product ID
        order_id: Optional order ID
    
    Returns:
        Updated product
    """
    service = PreUploadedService(db)
    
    if not order_id:
        # Just mark as used without order
        product = db.query(PreUploadedProduct).filter_by(id=product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pre-uploaded product {product_id} not found"
            )
        product.is_used = True
        db.commit()
        db.refresh(product)
    else:
        product = service.mark_product_as_used(product_id, order_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pre-uploaded product {product_id} not found or already used"
            )
    
    return {
        "id": product.id,
        "is_used": product.is_used,
        "used_at": product.used_at.isoformat() if product.used_at else None,
        "used_by_order_id": product.used_by_order_id,
    }


@router.put("/pre-uploaded-products/{product_id}/mark-unused")
async def mark_product_as_unused(
    product_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Mark a pre-uploaded product as unused.
    
    Args:
        product_id: Pre-uploaded product ID
    
    Returns:
        Updated product
    """
    product = db.query(PreUploadedProduct).filter_by(id=product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pre-uploaded product {product_id} not found"
        )
    
    product.is_used = False
    product.used_at = None
    product.used_by_order_id = None
    
    db.commit()
    db.refresh(product)
    
    return {
        "id": product.id,
        "is_used": product.is_used,
        "used_at": None,
        "used_by_order_id": None,
    }


@router.delete("/pre-uploaded-products/{product_id}")
async def delete_pre_uploaded_product(
    product_id: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a pre-uploaded product permanently.
    
    Args:
        product_id: Pre-uploaded product ID
    
    Returns:
        Success message
    """
    product = db.query(PreUploadedProduct).filter_by(id=product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pre-uploaded product {product_id} not found"
        )
    
    db.delete(product)
    db.commit()
    
    return {"message": f"Pre-uploaded product {product_id} deleted successfully"}
