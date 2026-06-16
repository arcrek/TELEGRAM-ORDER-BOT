"""
Notifications router for sending custom notifications to bot users.
"""
import os
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from telegram import Bot
from dotenv import load_dotenv
from src.dashboard.auth import get_current_admin, require_admin_role, get_db
from src.database.services.notification_service import NotificationService
from src.database.services.bot_user_service import BotUserService
from src.database.services.notification_settings_service import (
    NotificationSettingsService,
)
from src.database.services.order_notification_service import OrderNotificationService
from src.ipn import get_global_customer_bot
from src.bot.utils.bot_instance import get_shared_bot_instance
from src.utils.datetime_format import to_utc_iso

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter()


def get_bot_instance() -> Optional[Bot]:
    """
    Get bot instance for sending notifications.
    Tries multiple sources in order:
    1. Shared bot instance (if bot is running in same process)
    2. Global bot instance (if bot is running in same process)
    3. Create new bot instance from token (for separate processes)
    
    Returns:
        Bot instance or None if token not available
    """
    # Try shared instance first
    bot = get_shared_bot_instance()
    if bot:
        return bot
    
    # Try global instance
    bot = get_global_customer_bot()
    if bot:
        return bot
    
    # Create new instance from token (for separate processes)
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        try:
            logger.info("Creating bot instance from TELEGRAM_BOT_TOKEN")
            return Bot(token=bot_token)
        except Exception as e:
            logger.error(f"Failed to create bot instance from token: {str(e)}", exc_info=True)
            return None
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not found in environment variables")
    
    return None


class NotificationRequest(BaseModel):
    """Notification request schema."""
    message: str
    user_ids: Optional[List[int]] = None  # If provided, send to specific users only


class NotificationResponse(BaseModel):
    """Notification response schema."""
    success: bool
    total: int
    successful: int
    failed: int
    details: Optional[List[dict]] = None


class OrderNotificationSettingsResponse(BaseModel):
    """Response schema for order notification settings."""

    order_notify_enabled: bool
    order_notify_on_created: bool
    order_notify_on_paid: bool
    topup_notify_on_paid: bool
    whitelist_chat_ids: List[str]
    upgrade_chat_ids: List[str]
    topup_chat_ids: List[str]


class OrderNotificationSettingsUpdate(BaseModel):
    """Update payload for order notification settings."""

    order_notify_enabled: bool
    order_notify_on_created: bool
    order_notify_on_paid: bool
    topup_notify_on_paid: bool
    whitelist_chat_ids: List[str]
    upgrade_chat_ids: List[str]
    topup_chat_ids: List[str]


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    request: NotificationRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Send notification to users.
    Admin role required.
    
    Args:
        request: Notification request with message and optional user IDs
        current_admin: Current authenticated admin (must be admin role)
        db: Database session
    
    Returns:
        Notification response with delivery statistics
    """
    # Get bot instance (tries multiple sources)
    bot = get_bot_instance()
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot instance not available. Please ensure TELEGRAM_BOT_TOKEN is set in environment variables."
        )
    
    notification_service = NotificationService(db, bot=bot)
    
    if request.user_ids:
        # Send to specific users
        results = await notification_service.send_notification_to_multiple_users_async(
            telegram_user_ids=request.user_ids,
            message=request.message
        )
    else:
        # Send to all started users
        results = await notification_service.send_notification_to_all_started_async(request.message)
    
    return NotificationResponse(
        success=results["failed"] == 0,
        total=results["total"],
        successful=results["success"],
        failed=results["failed"],
        details=results.get("details")
    )


@router.post("/send/active", response_model=NotificationResponse)
async def send_notification_to_active(
    request: NotificationRequest,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db)
):
    """
    Send notification to active users only.
    Admin role required.
    
    Args:
        request: Notification request with message
        current_admin: Current authenticated admin (must be admin role)
        db: Database session
    
    Returns:
        Notification response with delivery statistics
    """
    # Get bot instance (tries multiple sources)
    bot = get_bot_instance()
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot instance not available. Please ensure TELEGRAM_BOT_TOKEN is set in environment variables."
        )
    
    notification_service = NotificationService(db, bot=bot)
    results = await notification_service.send_notification_to_active_users_async(request.message)
    
    return NotificationResponse(
        success=results["failed"] == 0,
        total=results["total"],
        successful=results["success"],
        failed=results["failed"],
        details=results.get("details")
    )


@router.get("/users")
async def list_bot_users(
    active_only: bool = False,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    List bot users (for notification targeting).
    
    Args:
        active_only: If True, return only active users
        current_admin: Current authenticated admin
        db: Database session
    
    Returns:
        List of bot users
    """
    bot_user_service = BotUserService(db)
    
    if active_only:
        users = bot_user_service.get_active_users()
    else:
        users = bot_user_service.get_all_started_users()
    
    return [
        {
            "id": user.id,
            "telegram_user_id": user.telegram_user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "has_started": user.has_started,
            "started_at": to_utc_iso(user.started_at),
            "is_active": user.is_active,
        }
        for user in users
    ]


@router.get("/order-settings", response_model=OrderNotificationSettingsResponse)
async def get_order_notification_settings(
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """
    Get global order notification settings.

    Admin role required.
    """
    settings_service = NotificationSettingsService(db)
    settings = settings_service.get_settings()
    whitelist_ids = settings_service.get_whitelist_entries(settings)
    upgrade_ids = settings_service.get_upgrade_entries(settings)
    topup_ids = settings_service.get_topup_entries(settings)

    return OrderNotificationSettingsResponse(
        order_notify_enabled=settings.order_notify_enabled,
        order_notify_on_created=settings.order_notify_on_created,
        order_notify_on_paid=settings.order_notify_on_paid,
        topup_notify_on_paid=settings.topup_notify_on_paid,
        whitelist_chat_ids=whitelist_ids,
        upgrade_chat_ids=upgrade_ids,
        topup_chat_ids=topup_ids,
    )


@router.put("/order-settings", response_model=OrderNotificationSettingsResponse)
async def update_order_notification_settings(
    payload: OrderNotificationSettingsUpdate,
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """
    Update global order notification settings.

    Admin role required.
    """
    settings_service = NotificationSettingsService(db)
    settings = settings_service.update_settings(
        order_notify_enabled=payload.order_notify_enabled,
        order_notify_on_created=payload.order_notify_on_created,
        order_notify_on_paid=payload.order_notify_on_paid,
        topup_notify_on_paid=payload.topup_notify_on_paid,
        whitelist_chat_ids=payload.whitelist_chat_ids,
        upgrade_chat_ids=payload.upgrade_chat_ids,
        topup_chat_ids=payload.topup_chat_ids,
    )
    whitelist_ids = settings_service.get_whitelist_entries(settings)
    upgrade_ids = settings_service.get_upgrade_entries(settings)
    topup_ids = settings_service.get_topup_entries(settings)

    return OrderNotificationSettingsResponse(
        order_notify_enabled=settings.order_notify_enabled,
        order_notify_on_created=settings.order_notify_on_created,
        order_notify_on_paid=settings.order_notify_on_paid,
        topup_notify_on_paid=settings.topup_notify_on_paid,
        whitelist_chat_ids=whitelist_ids,
        upgrade_chat_ids=upgrade_ids,
        topup_chat_ids=topup_ids,
    )


@router.post("/order-settings/test", response_model=NotificationResponse)
async def test_order_notification_settings(
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """
    Send a test notification using current order notification settings.

    Admin role required.
    """
    settings_service = NotificationSettingsService(db)
    settings = settings_service.get_settings()
    whitelist_targets = settings_service.get_whitelist_targets(settings)

    if not settings.order_notify_enabled or not whitelist_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Order notifications are disabled or whitelist is empty. "
                "Enable notifications and add at least one chat ID first."
            ),
        )

    bot = get_bot_instance()
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot instance not available. Please ensure TELEGRAM_BOT_TOKEN is set.",
        )

    order_notification_service = OrderNotificationService(db, bot=bot)
    test_message = "🔔 Test order notification.\nThis is a test from the dashboard settings."
    results = await order_notification_service.send_message_to_whitelist_async(
        targets=whitelist_targets,
        message=test_message,
    )

    return NotificationResponse(
        success=results["failed"] == 0,
        total=results["total"],
        successful=results["success"],
        failed=results["failed"],
        details=results.get("details"),
    )

