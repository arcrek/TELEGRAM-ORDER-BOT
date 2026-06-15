"""Manuals router — admin management of product user guides."""

import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ConfigDict
from src.dashboard.auth import get_current_admin, require_admin_role, get_db
from src.database.services.manual_service import ManualService
from src.database.models.product import Product


router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ManualCreate(BaseModel):
    title: str
    content: str = Field(..., max_length=4000)
    is_active: bool = True
    sort_order: int = 0
    product_ids: list[str] = []


class ManualUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = Field(None, max_length=4000)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    product_ids: Optional[list[str]] = None


class ManualResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    content: str
    is_active: bool
    sort_order: int
    assigned_product_ids: list[str]
    assigned_product_names: list[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_response(manual, db: Session) -> ManualResponse:
    """Build ManualResponse with product names resolved."""
    ids = [a.product_id for a in manual.product_assignments]
    products = db.query(Product).filter(Product.id.in_(ids)).all() if ids else []
    name_map = {p.id: p.name for p in products}
    return ManualResponse(
        id=manual.id,
        title=manual.title,
        content=manual.content,
        is_active=manual.is_active,
        sort_order=manual.sort_order,
        assigned_product_ids=ids,
        assigned_product_names=[name_map.get(i, "") for i in ids],
        created_at=manual.created_at,
        updated_at=manual.updated_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_manuals(
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """List all manuals."""
    service = ManualService(db)
    manuals = service.list_manuals()
    return [_build_response(m, db) for m in manuals]


@router.get("/{manual_id}", response_model=ManualResponse)
async def get_manual(
    manual_id: str,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """Get a single manual by ID."""
    service = ManualService(db)
    manual = service.get_manual_by_id(manual_id)
    if not manual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manual not found"
        )
    return _build_response(manual, db)


@router.post("", status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_manual(
    payload: ManualCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    """Create a new manual and optionally assign to products."""
    service = ManualService(db)
    manual_id = str(uuid.uuid4())
    manual = service.create_manual(
        {
            "id": manual_id,
            "title": payload.title,
            "content": payload.content,
            "is_active": payload.is_active,
            "sort_order": payload.sort_order,
        }
    )
    if payload.product_ids:
        service.set_assignments(manual.id, payload.product_ids)
        db.refresh(manual)
    return _build_response(manual, db)


@router.put("/{manual_id}", response_model=ManualResponse)
async def update_manual(
    manual_id: str,
    payload: ManualUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    """Update a manual."""
    service = ManualService(db)
    update_data = {}
    if payload.title is not None:
        update_data["title"] = payload.title
    if payload.content is not None:
        update_data["content"] = payload.content
    if payload.is_active is not None:
        update_data["is_active"] = payload.is_active
    if payload.sort_order is not None:
        update_data["sort_order"] = payload.sort_order

    manual = service.update_manual(manual_id, update_data)
    if not manual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manual not found"
        )

    if payload.product_ids is not None:
        service.set_assignments(manual_id, payload.product_ids)
        db.refresh(manual)

    return _build_response(manual, db)


@router.delete("/{manual_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manual(
    manual_id: str,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    """Delete a manual."""
    service = ManualService(db)
    success = service.delete_manual(manual_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manual not found"
        )
