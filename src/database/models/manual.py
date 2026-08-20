"""Manual (user guide) models."""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.models.base import Base


class Manual(Base):
    __tablename__ = "manuals"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    product_assignments = relationship(
        "ManualProductAssignment", back_populates="manual", cascade="all, delete-orphan"
    )


class ManualProductAssignment(Base):
    __tablename__ = "manual_product_assignments"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    manual_id = Column(
        String, ForeignKey("manuals.id", ondelete="CASCADE"), nullable=False
    )
    product_id = Column(
        String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    manual = relationship("Manual", back_populates="product_assignments")
    __table_args__ = (
        UniqueConstraint("manual_id", "product_id", name="uq_manual_product"),
        Index("ix_manual_product_assignments_product_id", "product_id"),
    )
