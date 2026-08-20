"""
Supplier order model.
"""
from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.models.base import Base
from src.database.models.enums import SupplierOrderStatus


class SupplierOrder(Base):
    """Supplier order model."""

    __tablename__ = "supplier_orders"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    status = Column(Enum(SupplierOrderStatus, native_enum=False), default=SupplierOrderStatus.PENDING, nullable=False)
    notification_message_id = Column(BigInteger, nullable=True)  # Telegram message ID sent to supplier
    supplier_response_message_id = Column(BigInteger, nullable=True)  # Supplier's reply message ID
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    order = relationship("Order", back_populates="supplier_orders")
    supplier = relationship("Supplier", back_populates="supplier_orders")

