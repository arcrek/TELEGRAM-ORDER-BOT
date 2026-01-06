"""
Order item model.
"""
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from src.database.models.base import Base


class OrderItem(Base):
    """Order item model."""

    __tablename__ = "order_items"

    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=True)  # Nullable to allow product deletion
    variation_id = Column(String, ForeignKey("product_variations.id"), nullable=True)  # Nullable to allow variation deletion
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)  # Price at time of order
    subtotal = Column(Integer, nullable=False)  # quantity × unit_price

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    variation = relationship("ProductVariation", back_populates="order_items")

