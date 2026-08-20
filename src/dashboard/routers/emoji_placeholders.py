"""Dashboard CRUD API for emoji placeholders."""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, computed_field
from sqlalchemy.orm import Session

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService

router = APIRouter()


class EmojiUnit(BaseModel):
    type: str  # 'text' | 'emoji'
    value: str | None = None
    emoji_id: str | None = None
    fallback: str | None = None


class EmojiPlaceholderResponse(BaseModel):
    id: int
    name: str
    configured: bool
    raw_text: str | None = None
    units: list[EmojiUnit] = []

    @computed_field
    @property
    def token(self) -> str:
        return f"{{emo:{self.id}}}"


class EmojiPlaceholderCreate(BaseModel):
    name: str


class EmojiPlaceholderUpdate(BaseModel):
    name: str


def _parse_units(content: str | None) -> list[EmojiUnit]:
    if not content:
        return []
    out: list[EmojiUnit] = []
    for u in json.loads(content):
        if u.get("t") == "emoji":
            out.append(EmojiUnit(type="emoji", emoji_id=str(u.get("id")), fallback=u.get("fb", "")))
        else:
            out.append(EmojiUnit(type="text", value=u.get("v", "")))
    return out


def _to_response(row) -> EmojiPlaceholderResponse:
    return EmojiPlaceholderResponse(
        id=row.id,
        name=row.name,
        configured=bool(row.content),
        raw_text=row.raw_text,
        units=_parse_units(row.content),
    )


@router.get("", response_model=list[EmojiPlaceholderResponse], include_in_schema=True)
@router.get("/", response_model=list[EmojiPlaceholderResponse], include_in_schema=False)
async def list_placeholders(
    current_admin=Depends(require_viewer_or_admin),
    db: Session = Depends(get_db),
):
    return [_to_response(r) for r in EmojiPlaceholderService(db).list_all()]


@router.post(
    "",
    response_model=EmojiPlaceholderResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=True,
)
@router.post(
    "/",
    response_model=EmojiPlaceholderResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_placeholder(
    payload: EmojiPlaceholderCreate,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    svc = EmojiPlaceholderService(db)
    pid = svc.create(payload.name)
    return _to_response(svc.get(pid))


@router.put("/{placeholder_id}", response_model=EmojiPlaceholderResponse)
async def rename_placeholder(
    placeholder_id: int,
    payload: EmojiPlaceholderUpdate,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    svc = EmojiPlaceholderService(db)
    try:
        row = svc.rename(placeholder_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(row)


@router.delete("/{placeholder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_placeholder(
    placeholder_id: int,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    if not EmojiPlaceholderService(db).delete(placeholder_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
