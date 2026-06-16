"""
Order model.
"""

from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Integer,
    DateTime,
    Enum,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.models.base import Base
from src.database.models.enums import OrderStatus


class Order(Base):
    """Order model."""

    __tablename__ = "orders"

    id = Column(String, primary_key=True)  # OrderID
    user_id = Column(BigInteger, nullable=False)  # Telegram user ID
    status = Column(
        Enum(OrderStatus, native_enum=False),
        default=OrderStatus.PENDING,
        nullable=False,
    )
    total_amount = Column(
        Integer, nullable=False
    )  # Actual charged total in VND (post-discount)
    discount_amount = Column(
        Integer, default=0, nullable=False
    )  # Total savings across all items

    # Payment tracking
    payment_provider = Column(String, nullable=True)  # "payos" | "pay2s"
    payment_transaction_id = Column(String, nullable=True)  # Pay2S transaction ID
    payment_message_ids = Column(
        Text, nullable=True
    )  # JSON list of Telegram message IDs to delete after payment

    # PayOS fields
    payos_order_code = Column(
        BigInteger, nullable=True, unique=True
    )  # PayOS orderCode (integer)
    payos_payment_link_id = Column(String, nullable=True)  # PayOS paymentLinkId
    payos_checkout_url = Column(Text, nullable=True)  # PayOS checkoutUrl (optional)
    payos_qr_code = Column(Text, nullable=True)  # PayOS VietQR EMV payload

    # UPGRADE delivery: flag flips True when IPN asks user for account info, cleared
    # by the bot once the user has replied and the message has been forwarded.
    awaiting_upgrade_info = Column(Boolean, default=False, nullable=False)

    # UPGRADE delivery: Telegram message ID of the account-info prompt the bot sent
    # to the customer. Stored so that later customer replies to that specific message
    # (even after awaiting_upgrade_info is cleared) are still forwarded to the admin.
    upgrade_prompt_msg_id = Column(BigInteger, nullable=True)

    # UPGRADE delivery: JSON list of {chat_id, thread_id, header_msg_id, forward_msg_id}
    # entries — message IDs of the bot's posts in each notification chat. Used to map
    # an admin's reply (in the notification chat) back to the originating order so the
    # bot can relay the admin's response to the customer.
    upgrade_forwards = Column(Text, nullable=True)

    refunded_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    supplier_orders = relationship("SupplierOrder", back_populates="order")
