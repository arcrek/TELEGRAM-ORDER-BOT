"""
Background task for auto-cancelling unpaid orders.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.database.connection import get_session_factory
from src.database.services.auto_cancel_service import AutoCancelService

logger = logging.getLogger(__name__)


class AutoCancelTask:
    """Background task for auto-cancelling unpaid orders."""
    
    def __init__(self, bot_instance=None, interval_minutes: int = 5):
        """
        Initialize auto-cancel task.
        
        Args:
            bot_instance: Telegram bot instance for sending notifications
            interval_minutes: How often to check for expired orders (default: 5 minutes)
        """
        self.bot = bot_instance
        self.interval_minutes = interval_minutes
        self.scheduler = BackgroundScheduler()
    
    def check_and_cancel_expired_orders(self):
        """Check for expired orders and topups and cancel them."""
        session_factory = get_session_factory()
        session = session_factory()

        try:
            auto_cancel_service = AutoCancelService(session, bot_instance=self.bot)

            # Cancel expired product orders.
            results = auto_cancel_service.process_expired_orders(
                minutes=30,
                send_notification=True
            )
            if results["found"] > 0:
                logger.info(
                    f"Auto-cancel task: Found {results['found']} expired orders, "
                    f"Cancelled {results['cancelled']}, Skipped {results['skipped']}"
                )

            # Cancel expired topup orders.
            topup_results = auto_cancel_service.process_expired_topups(
                minutes=30,
                send_notification=True
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

