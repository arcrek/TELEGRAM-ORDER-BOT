"""
Bonus tier model for product variations.
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.models.base import Base


class BonusTier(Base):
    """
    Bonus tier model.
    
    Represents a bonus configuration for a product variation.
    Example: Buy 10 items, get 2 free (min_quantity=10, bonus_quantity=2)
    """

    __tablename__ = "bonus_tiers"

    id = Column(String, primary_key=True)
    variation_id = Column(String, ForeignKey("product_variations.id", ondelete="CASCADE"), nullable=False)
    min_quantity = Column(Integer, nullable=False)  # Minimum quantity to qualify for bonus
    bonus_quantity = Column(Integer, nullable=False)  # Number of free items
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    variation = relationship("ProductVariation", back_populates="bonus_tiers")

    # Constraints
    __table_args__ = (
        UniqueConstraint('variation_id', 'min_quantity', name='uq_variation_min_quantity'),
        Index('ix_bonus_tiers_variation_id', 'variation_id'),
    )

    def __repr__(self):
        return f"<BonusTier(id={self.id}, variation_id={self.variation_id}, min={self.min_quantity}, bonus={self.bonus_quantity})>"
