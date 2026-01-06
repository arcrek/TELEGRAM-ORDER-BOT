"""
Order model.
"""
from sqlalchemy import Column, String, BigInteger, Integer, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.models.base import Base
from src.database.models.enums import OrderStatus


class Order(Base):
    """Order model."""

    __tablename__ = "orders"

    id = Column(String, primary_key=True)  # OrderID
    user_id = Column(BigInteger, nullable=False)  # Telegram user ID
    status = Column(Enum(OrderStatus, native_enum=False), default=OrderStatus.PENDING, nullable=False)
    total_amount = Column(Integer, nullable=False)  # Total in VND
    payment_transaction_id = Column(String, nullable=True)  # Pay2S transaction ID
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    supplier_orders = relationship("SupplierOrder", back_populates="order")

