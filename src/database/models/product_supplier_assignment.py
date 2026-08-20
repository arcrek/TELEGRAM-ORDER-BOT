"""
Product supplier assignment model.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.models.base import Base


class ProductSupplierAssignment(Base):
    """Product supplier assignment model."""

    __tablename__ = "product_supplier_assignments"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    product = relationship("Product", back_populates="supplier_assignments")
    supplier = relationship("Supplier", back_populates="product_assignments")

    # Unique constraint: one supplier can only be assigned to a product once
    __table_args__ = (
        UniqueConstraint('product_id', 'supplier_id', name='uq_product_supplier'),
    )

