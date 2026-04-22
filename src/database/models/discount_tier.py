"""
Discount tier model for product variations.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.models.base import Base


class DiscountTier(Base):
    """
    Discount tier model.

    Represents a quantity-based price discount for a product variation.
    discount_type='percentage': discount_value is 0-100 (e.g. 5 = 5% off total)
    discount_type='fixed_price': discount_value is override price per item in VND
    """

    __tablename__ = "discount_tiers"

    id = Column(String, primary_key=True)
    variation_id = Column(String, ForeignKey("product_variations.id", ondelete="CASCADE"), nullable=False)
    min_quantity = Column(Integer, nullable=False)
    discount_type = Column(String, nullable=False)   # 'percentage' | 'fixed_price'
    discount_value = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    variation = relationship("ProductVariation", back_populates="discount_tiers")

    __table_args__ = (
        UniqueConstraint('variation_id', 'min_quantity', name='uq_discount_variation_min_quantity'),
        Index('ix_discount_tiers_variation_id', 'variation_id'),
    )

    def __repr__(self):
        return (
            f"<DiscountTier(id={self.id}, variation_id={self.variation_id}, "
            f"min={self.min_quantity}, type={self.discount_type}, value={self.discount_value})>"
        )
