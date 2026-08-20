"""Blocked-users router — admin management of the user blocklist."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.services.block_service import BlockService

router = APIRouter()


class BlockedUserRow(BaseModel):
    id: int
    telegram_user_id: int | None
    username: str | None
    created_at: datetime


class BlockedUserListResponse(BaseModel):
    items: list[BlockedUserRow]
    total: int
    page: int
    per_page: int
    total_pages: int


class AddBlockRequest(BaseModel):
    identifier: str


class DeleteBlockResponse(BaseModel):
    success: bool


@router.get("", response_model=BlockedUserListResponse, include_in_schema=True)
@router.get("/", response_model=BlockedUserListResponse, include_in_schema=False)
async def list_blocked_users(
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin=Depends(require_viewer_or_admin),
):
    items, total = BlockService(db).list_blocked(
        search=search, page=page, per_page=per_page
    )
    return BlockedUserListResponse(
        items=[
            BlockedUserRow(
                id=row.id,
                telegram_user_id=row.telegram_user_id,
                username=row.username,
                created_at=row.created_at,
            )
            for row in items
        ],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
    )


@router.post("", response_model=BlockedUserRow, include_in_schema=True)
@router.post("/", response_model=BlockedUserRow, include_in_schema=False)
async def add_blocked_user(
    payload: AddBlockRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    try:
        row = BlockService(db).block(payload.identifier)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifier is required")
    return BlockedUserRow(
        id=row.id,
        telegram_user_id=row.telegram_user_id,
        username=row.username,
        created_at=row.created_at,
    )


@router.delete("/{block_id}", response_model=DeleteBlockResponse)
async def delete_blocked_user(
    block_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role),
):
    removed = BlockService(db).remove_block(block_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Block not found")
    return DeleteBlockResponse(success=True)
