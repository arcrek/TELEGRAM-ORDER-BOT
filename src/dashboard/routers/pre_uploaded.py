"""
Pre-uploaded product management router.
"""

from datetime import datetime, timezone
from typing import Literal

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.dashboard.auth import get_current_admin, get_db, require_admin_role
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.services.pre_uploaded_service import (
    EXPIRING_SOON_DAYS,
    PreUploadedService,
)
from src.utils.datetime_format import to_utc_iso

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
    used_at: str | None
    used_by_order_id: str | None
    created_at: str

    class Config:
        from_attributes = True


class BulkDeleteRequest(BaseModel):
    """Request schema for bulk deleting pre-uploaded products."""

    ids: list[str]


class DeleteByDateRequest(BaseModel):
    """Request schema for deleting unsold stock by upload date range."""

    product_id: str | None = None
    variation_id: str | None = None
    uploaded_from: str | None = None
    uploaded_to: str | None = None
    dry_run: bool = False


class ExportRequest(BaseModel):
    """Request schema for exporting (marking sold) available pre-uploaded stock."""

    product_id: str
    variation_id: str
    amount: int = Field(gt=0, le=1000)


class ExportResponse(BaseModel):
    """Response schema for the export endpoint."""

    requested: int
    exported: int
    short: bool  # True when exported < requested
    data: list[str]  # raw product_data strings, oldest-first


def _parse_date(raw: str, field: str) -> datetime:
    """Parse an ISO datetime string, raising 400 on failure."""
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format for '{field}': expected ISO 8601 string",
        )


def _apply_aging_filter(
    query,
    db: Session,
    aging_status: Literal["in_stock", "aging", "expiring_soon"],
):
    """
    Filter a PreUploadedProduct query to rows matching the requested aging bucket.

    Mirrors the cutoff logic in pre_uploaded_service.get_inventory_stats_by_product.
    Only unsold records can age, so is_used=False is enforced here.
    """
    now = datetime.now(timezone.utc)

    variants: list[ProductVariation] = db.query(ProductVariation).all()

    matching_ids: list[str] = []

    # Variants without thresholds: every unsold item counts as in_stock
    no_threshold_variation_ids: list[str] = []

    for variant in variants:
        tv = variant.warning_threshold_value
        tu = variant.warning_threshold_unit

        if tv is None or tu is None:
            no_threshold_variation_ids.append(variant.id)
            continue

        delta = relativedelta(**{tu: tv})  # type: ignore[arg-type]
        cutoff_aging = now - delta
        cutoff_expiring = now + relativedelta(days=EXPIRING_SOON_DAYS) - delta

        cutoff_aging_naive = cutoff_aging.replace(tzinfo=None)
        cutoff_expiring_naive = cutoff_expiring.replace(tzinfo=None)

        if aging_status == "aging":
            rows = (
                db.query(PreUploadedProduct.id)
                .filter(
                    PreUploadedProduct.variation_id == variant.id,
                    PreUploadedProduct.is_used.is_(False),
                    PreUploadedProduct.created_at <= cutoff_aging_naive,
                )
                .all()
            )
        elif aging_status == "expiring_soon":
            rows = (
                db.query(PreUploadedProduct.id)
                .filter(
                    PreUploadedProduct.variation_id == variant.id,
                    PreUploadedProduct.is_used.is_(False),
                    PreUploadedProduct.created_at > cutoff_aging_naive,
                    PreUploadedProduct.created_at <= cutoff_expiring_naive,
                )
                .all()
            )
        else:  # in_stock — not yet aging or expiring
            rows = (
                db.query(PreUploadedProduct.id)
                .filter(
                    PreUploadedProduct.variation_id == variant.id,
                    PreUploadedProduct.is_used.is_(False),
                    PreUploadedProduct.created_at > cutoff_expiring_naive,
                )
                .all()
            )

        matching_ids.extend(r[0] for r in rows)

    if aging_status == "in_stock":
        # Variants without thresholds are always "in_stock"
        rows_no_thresh = (
            db.query(PreUploadedProduct.id)
            .filter(
                PreUploadedProduct.variation_id.in_(no_threshold_variation_ids),
                PreUploadedProduct.is_used.is_(False),
            )
            .all()
        )
        matching_ids.extend(r[0] for r in rows_no_thresh)

    # aging always implies unsold
    query = query.filter(
        PreUploadedProduct.is_used.is_(False),
        PreUploadedProduct.id.in_(matching_ids),
    )
    return query


def _apply_common_filters(
    query,
    db: Session,
    product_id: str | None,
    variation_id: str | None,
    is_used: bool | None,
    uploaded_from: str | None,
    uploaded_to: str | None,
    aging_status: Literal["in_stock", "aging", "expiring_soon"] | None,
    data_search: str | None = None,
):
    """Apply all shared filter params to a PreUploadedProduct query."""
    if product_id:
        query = query.filter(PreUploadedProduct.product_id == product_id)
    if variation_id:
        query = query.filter(PreUploadedProduct.variation_id == variation_id)
    if is_used is not None:
        query = query.filter(PreUploadedProduct.is_used == is_used)
    if uploaded_from:
        dt = _parse_date(uploaded_from, "uploaded_from")
        query = query.filter(PreUploadedProduct.created_at >= dt.replace(tzinfo=None))
    if uploaded_to:
        dt = _parse_date(uploaded_to, "uploaded_to")
        query = query.filter(PreUploadedProduct.created_at <= dt.replace(tzinfo=None))
    if aging_status:
        # aging_status only meaningful for unsold; is_used filter applied inside helper
        query = _apply_aging_filter(query, db, aging_status)
    if data_search:
        query = query.filter(PreUploadedProduct.product_data.ilike(f"%{data_search}%"))
    return query


@router.get("/pre-uploaded-products")
async def list_pre_uploaded_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    product_id: str | None = Query(None),
    variation_id: str | None = Query(None),
    is_used: bool | None = Query(None),
    uploaded_from: str | None = Query(None),
    uploaded_to: str | None = Query(None),
    aging_status: Literal["in_stock", "aging", "expiring_soon"] | None = Query(None),
    data_search: str | None = Query(None),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List pre-uploaded products with filters."""
    query = db.query(PreUploadedProduct)
    query = _apply_common_filters(
        query,
        db,
        product_id,
        variation_id,
        is_used,
        uploaded_from,
        uploaded_to,
        aging_status,
        data_search,
    )

    total = query.count()
    offset = (page - 1) * per_page
    products = query.offset(offset).limit(per_page).all()

    # Enrich with product and variation names
    result = []
    for p in products:
        product = db.query(Product).filter_by(id=p.product_id).first()
        variation = db.query(ProductVariation).filter_by(id=p.variation_id).first()

        result.append(
            {
                "id": p.id,
                "product_id": p.product_id,
                "product_name": product.name if product else "Unknown",
                "variation_id": p.variation_id,
                "variation_name": variation.name if variation else "Unknown",
                "product_data": p.product_data,
                "is_used": p.is_used,
                "used_at": to_utc_iso(p.used_at),
                "used_by_order_id": p.used_by_order_id,
                "created_at": to_utc_iso(p.created_at),
            }
        )

    return {
        "items": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


@router.get("/pre-uploaded-products/inventory-stats")
async def get_inventory_stats(
    current_admin=Depends(get_current_admin), db: Session = Depends(get_db)
):
    """
    Get per-variant inventory statistics for all PRE_UPLOADED products.

    Returns:
        List of products with variant-level stock, aging, and expiring_soon counts.
    """
    service = PreUploadedService(db)
    products = service.get_inventory_stats_by_product()
    return {"products": products}


@router.get("/pre-uploaded-products/statistics")
async def get_pre_uploaded_statistics(
    product_id: str | None = Query(None),
    variation_id: str | None = Query(None),
    is_used: bool | None = Query(None),
    uploaded_from: str | None = Query(None),
    uploaded_to: str | None = Query(None),
    aging_status: Literal["in_stock", "aging", "expiring_soon"] | None = Query(None),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get pre-uploaded product statistics, scoped to active filters."""
    base = db.query(PreUploadedProduct)
    base = _apply_common_filters(
        base,
        db,
        product_id,
        variation_id,
        is_used,
        uploaded_from,
        uploaded_to,
        aging_status,
    )

    total = base.count()
    used = base.filter(PreUploadedProduct.is_used.is_(True)).count()
    available = base.filter(PreUploadedProduct.is_used.is_(False)).count()

    # by_product: iterate over products that have matching rows
    products = db.query(Product).all()
    by_product = {}
    for product in products:
        prod_query = _apply_common_filters(
            db.query(PreUploadedProduct).filter(
                PreUploadedProduct.product_id == product.id
            ),
            db,
            None,
            variation_id,
            is_used,
            uploaded_from,
            uploaded_to,
            aging_status,
        )
        count = prod_query.count()
        if count > 0:
            by_product[product.id] = {
                "product_id": product.id,
                "product_name": product.name,
                "total": count,
                "used": prod_query.filter(PreUploadedProduct.is_used.is_(True)).count(),
                "available": prod_query.filter(
                    PreUploadedProduct.is_used.is_(False)
                ).count(),
            }

    return {
        "total": total,
        "used": used,
        "available": available,
        "by_product": by_product,
    }


@router.post("/pre-uploaded-products/export", response_model=ExportResponse)
async def export_pre_uploaded_products(
    request: ExportRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """
    Atomically mark up to `amount` available rows as sold and return their data.

    Exported rows are distinguishable from order-fulfilled rows: is_used=True but
    used_by_order_id=NULL.  Short stock (fewer available than requested) is returned
    as a partial export with short=True — never a hard error.
    Zero available → exported=0, short=True (not an HTTP error).
    """
    # Validate variation belongs to the requested product
    variation = db.query(ProductVariation).filter_by(id=request.variation_id).first()
    if not variation or variation.product_id != request.product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Variation does not belong to the specified product",
        )

    rows = PreUploadedService(db).export_available_products(
        request.product_id, request.variation_id, request.amount
    )
    data = [r.product_data for r in rows]
    return ExportResponse(
        requested=request.amount,
        exported=len(rows),
        short=len(rows) < request.amount,
        data=data,
    )


@router.post("/pre-uploaded-products/delete-by-date")
async def delete_pre_uploaded_by_date(
    request: DeleteByDateRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """
    Preview or delete unsold pre-uploaded stock matching an upload date range.

    Always restricted to is_used=False (unsold only).
    Requires at least one of uploaded_from or uploaded_to to prevent accidental full wipe.
    """
    if not request.uploaded_from and not request.uploaded_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of uploaded_from or uploaded_to is required",
        )

    # Safety invariant: only unsold items are ever deleted
    query = db.query(PreUploadedProduct).filter(PreUploadedProduct.is_used.is_(False))

    if request.product_id:
        query = query.filter(PreUploadedProduct.product_id == request.product_id)
    if request.variation_id:
        query = query.filter(PreUploadedProduct.variation_id == request.variation_id)
    if request.uploaded_from:
        dt = _parse_date(request.uploaded_from, "uploaded_from")
        query = query.filter(PreUploadedProduct.created_at >= dt.replace(tzinfo=None))
    if request.uploaded_to:
        dt = _parse_date(request.uploaded_to, "uploaded_to")
        query = query.filter(PreUploadedProduct.created_at <= dt.replace(tzinfo=None))

    if request.dry_run:
        return {"matching": query.count()}

    deleted = query.delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


@router.put("/pre-uploaded-products/{product_id}/mark-used")
async def mark_product_as_used(
    product_id: str,
    order_id: str | None = None,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """
    Mark a pre-uploaded product as used (sold).

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
                detail=f"Pre-uploaded product {product_id} not found",
            )
        # Manual override: mark as sold without linking to an order
        product.is_used = True
        if not product.used_at:
            product.used_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(product)
    else:
        product = service.mark_product_as_used(product_id, order_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pre-uploaded product {product_id} not found or already used",
            )

    return {
        "id": product.id,
        "is_used": product.is_used,
        "used_at": to_utc_iso(product.used_at),
        "used_by_order_id": product.used_by_order_id,
    }


@router.put("/pre-uploaded-products/{product_id}/mark-unused")
async def mark_product_as_unused(
    product_id: str,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
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
            detail=f"Pre-uploaded product {product_id} not found",
        )

    # Prevent making a sold item available again.
    # Once it has been consumed by an order, it must remain sold.
    if product.used_by_order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark product {product_id} as available because it was sold in order {product.used_by_order_id}",
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
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
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
            detail=f"Pre-uploaded product {product_id} not found",
        )

    db.delete(product)
    db.commit()

    return {"message": f"Pre-uploaded product {product_id} deleted successfully"}


@router.post("/pre-uploaded-products/bulk-delete")
async def bulk_delete_pre_uploaded_products(
    request: BulkDeleteRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """
    Bulk delete pre-uploaded products permanently.

    Args:
        request: BulkDeleteRequest containing list of pre-uploaded product IDs.

    Returns:
        Dictionary with number of deleted products.
    """
    if not request.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No product IDs provided for deletion",
        )

    # Find all products matching the provided IDs
    products = (
        db.query(PreUploadedProduct)
        .filter(PreUploadedProduct.id.in_(request.ids))
        .all()
    )

    if not products:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching pre-uploaded products found for provided IDs",
        )

    deleted_count = 0
    for product in products:
        db.delete(product)
        deleted_count += 1

    db.commit()

    return {"deleted": deleted_count}
