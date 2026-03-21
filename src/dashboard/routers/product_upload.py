"""
Product upload router.
"""
import os
import asyncio
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from telegram import Bot
from src.dashboard.auth import get_current_admin, get_db
from src.database.services.product_upload_service import ProductUploadService
from src.database.services.notification_service import NotificationService
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.connection import get_session_factory
from src.ipn import get_global_customer_bot
from src.bot.utils.bot_instance import get_shared_bot_instance

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_bot_instance() -> Optional[Bot]:
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
        except Exception as e:
            logger.error(f"Failed to create bot instance for upload notification: {e}")
    return None


def _collect_upload_notification_messages(
    db: Session,
    products_data: List[Dict[str, Any]],
    result: Dict[str, Any],
) -> List[str]:
    """
    Build one notification message per unique variation that was successfully uploaded.

    Must be called before the DB session closes so relationships are accessible.
    """
    system_name = os.getenv("SYSTEM_NAME", "MUATAIKHOANPRO")

    failed_indices = {e["index"] for e in result.get("errors", [])}
    successful_items = [
        item for idx, item in enumerate(products_data) if idx not in failed_indices
    ]

    # Count uploaded quantity per (product_id, variation_id)
    variation_counts: Dict[tuple, int] = {}
    for item in successful_items:
        key = (item["product_id"], item["variation_id"])
        variation_counts[key] = variation_counts.get(key, 0) + 1

    messages = []
    for (product_id, variation_id), uploaded_qty in variation_counts.items():
        product = db.query(Product).filter_by(id=product_id).first()
        variation = db.query(ProductVariation).filter_by(id=variation_id).first()
        if not product or not variation:
            continue

        total_qty = (
            db.query(PreUploadedProduct)
            .filter_by(variation_id=variation_id, is_used=False)
            .count()
        )

        price_str = f"{variation.price:,}đ"
        message = (
            f"📢 {system_name} thông báo có hàng mới!\n\n"
            f"Sản phẩm: {product.name} {variation.name} {price_str}\n"
            f"➕ Đã thêm: {uploaded_qty}\n"
            f"📦 Tổng số lượng: {total_qty}\n\n"
            f"👉 /products để mua hàng"
        )
        messages.append(message)

    return messages


async def _send_upload_notifications(messages: List[str]) -> None:
    """Broadcast each upload notification message to all started users."""
    try:
        bot = _get_bot_instance()
        if not bot:
            logger.warning("No bot instance available; skipping upload notifications")
            return

        session_factory = get_session_factory()
        for message in messages:
            session = session_factory()
            try:
                notification_service = NotificationService(session, bot=bot)
                await notification_service.send_notification_to_all_started_async(message)
            except Exception as e:
                logger.error(f"Failed to send upload notification: {e}", exc_info=True)
            finally:
                session.close()
    except Exception as e:
        logger.error(f"Unexpected error in upload notification task: {e}", exc_info=True)


class ParseTextRequest(BaseModel):
    """Parse text content request schema."""
    content: str
    format_type: str = "line_separated"  # line_separated, key_value, csv


class ParseTextResponse(BaseModel):
    """Parse text content response schema."""
    parsed_data: List[dict]
    format_type: str
    item_count: int


class ProductUploadItem(BaseModel):
    """Product upload item schema."""
    product_id: str
    variation_id: str
    product_data: str


class BulkUploadRequest(BaseModel):
    """Bulk upload request schema."""
    products: List[ProductUploadItem]


class BulkUploadResponse(BaseModel):
    """Bulk upload response schema."""
    success: int
    failed: int
    errors: List[dict]


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
    
    result = service.bulk_import_products(products_data)

    if result["success"] > 0:
        messages = _collect_upload_notification_messages(db, products_data, result)
        if messages:
            asyncio.create_task(_send_upload_notifications(messages))

    return {
        "success": result["success"],
        "failed": result["failed"],
        "errors": result["errors"],
    }


@router.post("/products/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    format_type: Optional[str] = None,
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
    if not file.filename.endswith('.txt'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt files are supported"
        )
    
    # Read file content
    content = await file.read()
    content_str = content.decode('utf-8')
    
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
            detail=f"Failed to parse file: {str(e)}"
        )
    
    # For now, return parsed data
    # In a real implementation, you'd need to map parsed data to products
    return {
        "parsed_data": parsed_data,
        "format_type": format_type,
        "item_count": len(parsed_data),
        "message": "File parsed successfully. Please map fields to products."
    }

