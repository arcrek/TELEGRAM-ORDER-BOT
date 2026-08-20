"""
Product upload router.
"""
import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from src.bot.messages.emoji_renderer import render as render_emoji
from src.bot.utils.bot_instance import get_shared_bot_instance
from src.dashboard.auth import get_current_admin, get_db
from src.database.connection import get_session_factory
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.services.app_settings_service import AppSettingsService
from src.database.services.bot_ui_settings_service import BotUiSettingsService
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.product_upload_service import ProductUploadService
from src.ipn import get_global_customer_bot

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_bot_instance() -> Bot | None:
    """Get bot instance for sending upload notifications."""
    bot = get_shared_bot_instance()
    if bot:
        return bot
    bot = get_global_customer_bot()
    if bot:
        return bot
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        try:
            return Bot(token=bot_token)
        except Exception:
            logger.exception("Failed to create bot instance for upload notification")
    return None


def _collect_upload_notification_messages(
    db: Session,
    products_data: list[dict[str, Any]],
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build one notification entry per unique variation that was successfully uploaded.

    Must be called before the DB session closes so relationships are accessible.

    Returns a list of dicts with keys: "message" (str) and "product_id" (str).
    """
    ui_settings = BotUiSettingsService(db).get_settings()
    system_name = AppSettingsService(db).get_settings().system_name
    default_header = f"📢 {system_name} thông báo có hàng mới!"
    header = ui_settings.upload_notification_header or default_header

    error_indices = {e["index"] for e in result.get("errors", [])}
    successful_items = [
        item for idx, item in enumerate(products_data) if idx not in error_indices
    ]

    # Count uploaded quantity per (product_id, variation_id)
    variation_counts: dict[tuple, int] = {}
    for item in successful_items:
        key = (item["product_id"], item["variation_id"])
        variation_counts[key] = variation_counts.get(key, 0) + 1

    entries = []
    for (product_id, variation_id), uploaded_qty in variation_counts.items():
        total_qty = (
            db.query(PreUploadedProduct)
            .filter_by(variation_id=variation_id, is_used=False)
            .count()
        )
        entry = _build_upload_notification_entry(
            db, product_id, variation_id, uploaded_qty, total_qty, header
        )
        if entry:
            entries.append(entry)

    return entries


def _build_upload_notification_entry(
    db: Session,
    product_id: str,
    variation_id: str,
    added_qty: int,
    total_qty: int,
    header: str | None = None,
) -> dict[str, Any] | None:
    """Build the shared new-stock notification used by uploads and fixed stock."""
    product = db.query(Product).filter_by(id=product_id).first()
    variation = db.query(ProductVariation).filter_by(id=variation_id).first()
    if not product or not variation:
        return None

    if header is None:
        settings = BotUiSettingsService(db).get_settings()
        header = settings.upload_notification_header or (
            f"📢 {os.getenv('SYSTEM_NAME', 'MUATAIKHOANPRO')} thông báo có hàng mới!"
        )

    return {
        "message": (
            f"{header}\n\n"
            f"Sản phẩm: {product.name} {variation.name} {variation.price:,}đ\n"
            f"➕ Đã thêm: {added_qty}\n"
            f"📦 Tổng số lượng: {total_qty}"
        ),
        "product_id": product_id,
    }


async def _send_upload_notifications(entries: list[dict[str, Any]]) -> None:
    """Broadcast each upload notification to all started users with action buttons."""
    try:
        bot = _get_bot_instance()
        if not bot:
            logger.warning("No bot instance available; skipping upload notifications")
            return

        session_factory = get_session_factory()
        from src.database.services.bot_user_service import BotUserService

        for entry in entries:
            message = entry["message"]
            product_id = entry.get("product_id", "")

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🛒 Mua ngay / Buy now",
                        callback_data=f"product_{product_id}",
                    ),
                    InlineKeyboardButton(
                        "📋 Danh sách sản phẩm / Product list",
                        callback_data="show_products_list",
                    ),
                ]
            ])

            session = session_factory()
            try:
                users = BotUserService(session).get_all_started_users()
                # Expand {emo:id} placeholders (header + product/variation names)
                # to <tg-emoji> HTML once for the whole broadcast.
                rendered, parse_mode = render_emoji(message, EmojiPlaceholderService(session))
                send_kwargs = {"text": rendered, "reply_markup": keyboard}
                if parse_mode is not None:
                    send_kwargs["parse_mode"] = parse_mode
                for user in users:
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_user_id,
                            **send_kwargs,
                        )
                    except TelegramError as e:
                        logger.warning(
                            f"Failed to send upload notification to {user.telegram_user_id}: {e}"
                        )
            # Outer boundary: DB reads (users, emoji placeholders) plus the whole
            # per-user send loop above — one broadcast failing must not crash
            # the upload endpoint.
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to send upload notification batch: {e}")
            finally:
                session.close()
    except Exception:
        logger.exception("Unexpected error in upload notification task")


class ParseTextRequest(BaseModel):
    """Parse text content request schema."""
    content: str
    format_type: str = "line_separated"  # line_separated, key_value, csv


class ParseTextResponse(BaseModel):
    """Parse text content response schema."""
    parsed_data: list[dict]
    format_type: str
    item_count: int


class ProductUploadItem(BaseModel):
    """Product upload item schema."""
    product_id: str
    variation_id: str
    product_data: str


class DuplicateCheckItem(BaseModel):
    """Single item for duplicate checking."""
    product_id: str
    variation_id: str
    product_data: str


class DuplicateCheckRequest(BaseModel):
    """Request body for duplicate check."""
    products: list[DuplicateCheckItem]


class DuplicateCheckResponse(BaseModel):
    """Response for duplicate check."""
    duplicate_count: int
    unique_count: int
    total: int
    duplicates: list[dict]


class BulkUploadRequest(BaseModel):
    """Bulk upload request schema."""
    products: list[ProductUploadItem]
    skip_duplicates: bool = False


class BulkUploadResponse(BaseModel):
    """Bulk upload response schema."""
    success: int
    failed: int
    duplicates_skipped: int = 0
    errors: list[dict]


@router.post("/products/upload/parse", response_model=ParseTextResponse)
async def parse_text_content(
    request: ParseTextRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Parse text content for product upload.
    
    Args:
        request: Parse request with content and format type
    
    Returns:
        Parsed data
    """
    service = ProductUploadService(db)
    
    try:
        parsed_data = service.parse_text_content(
            request.content,
            request.format_type
        )
        
        return {
            "parsed_data": parsed_data,
            "format_type": request.format_type,
            "item_count": len(parsed_data),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/products/upload/check-duplicates", response_model=DuplicateCheckResponse)
async def check_duplicate_products(
    request: DuplicateCheckRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Check how many of the given products already exist in the database (unused).

    Returns the count of duplicates and the list of duplicate entries so the
    frontend can warn the admin before the actual upload.
    """
    service = ProductUploadService(db)
    products_data = [
        {
            "product_id": p.product_id,
            "variation_id": p.variation_id,
            "product_data": p.product_data,
        }
        for p in request.products
    ]
    result = service.check_duplicates(products_data)
    return DuplicateCheckResponse(
        duplicate_count=len(result["duplicates"]),
        unique_count=result["unique_count"],
        total=len(products_data),
        duplicates=result["duplicates"],
    )


@router.post("/products/upload", response_model=BulkUploadResponse)
async def upload_products(
    request: BulkUploadRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Bulk upload products.
    
    Args:
        request: Bulk upload request with products list
    
    Returns:
        Upload results
    """
    service = ProductUploadService(db)
    
    products_data = [
        {
            "product_id": p.product_id,
            "variation_id": p.variation_id,
            "product_data": p.product_data,
        }
        for p in request.products
    ]
    
    result = service.bulk_import_products(products_data, skip_duplicates=request.skip_duplicates)

    if result["success"] > 0:
        messages = _collect_upload_notification_messages(db, products_data, result)
        if messages:
            asyncio.create_task(_send_upload_notifications(messages))

    return {
        "success": result["success"],
        "failed": result["failed"],
        "duplicates_skipped": result.get("duplicates_skipped", 0),
        "errors": result["errors"],
    }


@router.post("/products/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    format_type: str | None = None,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Upload products from file.
    
    Args:
        file: Uploaded file
        format_type: Format type (auto-detected if not provided)
    
    Returns:
        Upload results
    """
    # Validate file type
    if not file.filename.endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt files are supported"
        )
    
    # Read file content
    content = await file.read()
    content_str = content.decode("utf-8")
    
    service = ProductUploadService(db)
    
    # Auto-detect format if not provided
    if not format_type:
        format_type = service.detect_format(content_str)
    
    # Parse content
    try:
        parsed_data = service.parse_text_content(content_str, format_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {e!s}"
        )
    
    # For now, return parsed data
    # In a real implementation, you'd need to map parsed data to products
    return {
        "parsed_data": parsed_data,
        "format_type": format_type,
        "item_count": len(parsed_data),
        "message": "File parsed successfully. Please map fields to products."
    }
