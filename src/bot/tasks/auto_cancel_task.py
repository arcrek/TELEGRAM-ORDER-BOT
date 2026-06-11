"""
Background task for auto-cancelling unpaid orders and warning users before expiry.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.database.connection import get_session_factory
from src.database.services.auto_cancel_service import AutoCancelService, PAYMENT_EXPIRE_MINUTES

logger = logging.getLogger(__name__)


class AutoCancelTask:
    """Background task for auto-cancelling unpaid orders."""

    def __init__(self, bot_instance=None, interval_minutes: int = 1, main_loop=None):
        """
        Initialize auto-cancel task.

        Args:
            bot_instance: Telegram bot instance for sending notifications
            interval_minutes: How often to check (default: 1 minute for 1-min warning accuracy)
            main_loop: Optional asyncio loop the bot runs on
        """
        self.bot = bot_instance
        self.interval_minutes = interval_minutes
        self.main_loop = main_loop
        self.scheduler = BackgroundScheduler()
        # In-memory sets to prevent duplicate warnings within a process lifetime.
        self._warned_order_ids: set = set()
        self._warned_topup_ids: set = set()

    def check_and_cancel_expired_orders(self):
        """Check for expiring orders (warn) and expired orders (cancel)."""
        session_factory = get_session_factory()
        session = session_factory()

        try:
            auto_cancel_service = AutoCancelService(
                session, bot_instance=self.bot, main_loop=self.main_loop
            )

            # Send 1-minute warnings before expiry.
            warn_results = auto_cancel_service.process_expiring_soon(
                self._warned_order_ids,
                self._warned_topup_ids,
            )
            if warn_results["orders_warned"] or warn_results["topups_warned"]:
                logger.info(
                    f"Expiry warnings sent: {warn_results['orders_warned']} orders, "
                    f"{warn_results['topups_warned']} topups"
                )

            # Cancel expired product orders.
            results = auto_cancel_service.process_expired_orders(
                minutes=PAYMENT_EXPIRE_MINUTES,
                send_notification=True,
            )
            if results["found"] > 0:
                logger.info(
                    f"Auto-cancel task: Found {results['found']} expired orders, "
                    f"Cancelled {results['cancelled']}, Skipped {results['skipped']}"
                )

            # Cancel expired topup orders.
            topup_results = auto_cancel_service.process_expired_topups(
                minutes=PAYMENT_EXPIRE_MINUTES,
                send_notification=True,
            )
            if topup_results["found"] > 0:
                logger.info(
                    f"Auto-cancel task (topups): Found {topup_results['found']} expired topups, "
                    f"Cancelled {topup_results['cancelled']}, Skipped {topup_results['skipped']}"
                )
        except Exception as e:
            logger.error(f"Error in auto-cancel task: {str(e)}", exc_info=True)
        finally:
            session.close()

    def start(self):
        """Start the auto-cancel scheduler."""
        self.scheduler.add_job(
            self.check_and_cancel_expired_orders,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id="auto_cancel_orders",
            name="Auto-cancel expired orders",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"Auto-cancel task started (checking every {self.interval_minutes} minutes)")

    def stop(self):
        """Stop the auto-cancel scheduler."""
        self.scheduler.shutdown()
        logger.info("Auto-cancel task stopped")

