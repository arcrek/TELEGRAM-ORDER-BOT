"""
Bonus tier service for managing bonus configurations.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.bonus_tier import BonusTier
from src.database.models.product_variation import ProductVariation


class BonusTierService:
    """Service for managing bonus tiers."""

    def __init__(self, session: Session):
        """
        Initialize the service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def create_bonus_tier(
        self,
        variation_id: str,
        min_quantity: int,
        bonus_quantity: int,
        is_active: bool = True,
        tier_id: str | None = None,
    ) -> BonusTier:
        """
        Create a new bonus tier.
        
        Args:
            variation_id: ID of the product variation
            min_quantity: Minimum quantity to qualify for bonus
            bonus_quantity: Number of free items
            is_active: Whether the tier is active
            tier_id: Optional custom ID (auto-generated if not provided)
        
        Returns:
            Created BonusTier instance
        
        Raises:
            ValueError: If variation doesn't exist or min_quantity already exists
        """
        # Validate variation exists
        variation = self.session.query(ProductVariation).filter_by(id=variation_id).first()
        if not variation:
            raise ValueError(f"Variation with ID {variation_id} not found")
        
        # Check for duplicate min_quantity
        existing = self.session.query(BonusTier).filter_by(
            variation_id=variation_id,
            min_quantity=min_quantity
        ).first()
        if existing:
            raise ValueError(f"Bonus tier with min_quantity {min_quantity} already exists for this variation")
        
        # Generate ID if not provided
        if not tier_id:
            tier_id = f"bonus_{uuid.uuid4().hex[:12]}"
        
        bonus_tier = BonusTier(
            id=tier_id,
            variation_id=variation_id,
            min_quantity=min_quantity,
            bonus_quantity=bonus_quantity,
            is_active=is_active,
        )
        
        self.session.add(bonus_tier)
        self.session.commit()
        self.session.refresh(bonus_tier)
        
        return bonus_tier

    def get_bonus_tier_by_id(self, tier_id: str) -> BonusTier | None:
        """
        Get a bonus tier by ID.
        
        Args:
            tier_id: Bonus tier ID
        
        Returns:
            BonusTier instance or None if not found
        """
        return self.session.query(BonusTier).filter_by(id=tier_id).first()

    def get_bonus_tiers_by_variation(
        self,
        variation_id: str,
        only_active: bool = True,
    ) -> list[BonusTier]:
        """
        Get all bonus tiers for a variation, sorted by min_quantity ascending.
        
        Args:
            variation_id: ID of the product variation
            only_active: If True, only return active tiers
        
        Returns:
            List of BonusTier instances sorted by min_quantity
        """
        query = self.session.query(BonusTier).filter_by(variation_id=variation_id)
        
        if only_active:
            query = query.filter_by(is_active=True)
        
        return query.order_by(BonusTier.min_quantity.asc()).all()

    def update_bonus_tier(
        self,
        tier_id: str,
        update_data: dict[str, Any],
    ) -> BonusTier | None:
        """
        Update a bonus tier.
        
        Args:
            tier_id: Bonus tier ID
            update_data: Dictionary of fields to update
        
        Returns:
            Updated BonusTier instance or None if not found
        
        Raises:
            ValueError: If trying to set duplicate min_quantity
        """
        bonus_tier = self.get_bonus_tier_by_id(tier_id)
        if not bonus_tier:
            return None
        
        # Check for duplicate min_quantity if being updated
        if 'min_quantity' in update_data:
            new_min = update_data['min_quantity']
            existing = self.session.query(BonusTier).filter(
                BonusTier.variation_id == bonus_tier.variation_id,
                BonusTier.min_quantity == new_min,
                BonusTier.id != tier_id
            ).first()
            if existing:
                raise ValueError(f"Bonus tier with min_quantity {new_min} already exists for this variation")
        
        # Update allowed fields
        allowed_fields = ['min_quantity', 'bonus_quantity', 'is_active']
        for field, value in update_data.items():
            if field in allowed_fields and value is not None:
                setattr(bonus_tier, field, value)
        
        self.session.commit()
        self.session.refresh(bonus_tier)
        
        return bonus_tier

    def delete_bonus_tier(self, tier_id: str) -> bool:
        """
        Delete a bonus tier.
        
        Args:
            tier_id: Bonus tier ID
        
        Returns:
            True if deleted, False if not found
        """
        bonus_tier = self.get_bonus_tier_by_id(tier_id)
        if not bonus_tier:
            return False
        
        self.session.delete(bonus_tier)
        self.session.commit()
        
        return True

    def get_applicable_bonus(
        self,
        variation_id: str,
        quantity: int,
        stock: int,
    ) -> BonusTier | None:
        """
        Get the best applicable bonus tier that fits within available stock.
        
        Finds the highest tier where:
        1. quantity >= min_quantity (user qualifies for bonus)
        2. quantity + bonus_quantity <= stock (total fits in stock)
        
        Args:
            variation_id: Variation ID
            quantity: Order quantity
            stock: Available stock
        
        Returns:
            BonusTier if applicable and fits stock, None otherwise
        """
        tiers = self.get_bonus_tiers_by_variation(variation_id, only_active=True)
        
        if not tiers:
            return None
        
        # Find the highest tier that qualifies and fits stock
        # Sort by min_quantity descending to get the best (highest) tier first
        applicable_tier = None
        for tier in sorted(tiers, key=lambda t: t.min_quantity, reverse=True):
            if quantity >= tier.min_quantity:
                total_items = quantity + tier.bonus_quantity
                if total_items <= stock:
                    applicable_tier = tier
                    break
                # If bonus exceeds stock, continue to try lower tiers
        
        return applicable_tier

    def calculate_total_items(self, quantity: int, bonus_quantity: int) -> int:
        """
        Calculate total items including bonus.
        
        Args:
            quantity: Order quantity
            bonus_quantity: Bonus quantity
        
        Returns:
            Total items (quantity + bonus)
        """
        return quantity + bonus_quantity

    def get_max_orderable_quantity(
        self,
        variation_id: str,
        stock: int,
    ) -> int:
        """
        Get the maximum quantity a user can order considering bonus.
        
        This helps determine how many items can be ordered without
        exceeding stock when bonus is applied.
        
        Args:
            variation_id: Variation ID
            stock: Available stock
        
        Returns:
            Maximum orderable quantity
        """
        tiers = self.get_bonus_tiers_by_variation(variation_id, only_active=True)
        
        if not tiers:
            # No bonus, max is just stock
            return stock
        
        # Check each tier from highest min_quantity to lowest
        for tier in sorted(tiers, key=lambda t: t.min_quantity, reverse=True):
            # If ordering min_quantity + bonus fits in stock, that's valid
            total_with_bonus = tier.min_quantity + tier.bonus_quantity
            if total_with_bonus <= stock:
                # Can order up to stock - bonus_quantity to leave room for bonus
                return stock - tier.bonus_quantity
        
        # No tier fits, return stock
        return stock

    def format_bonus_display(
        self,
        variation_id: str,
        language: str = 'vi',
    ) -> str:
        """
        Format bonus display text for a variation.
        
        Returns the first (smallest min_quantity) bonus tier text.
        
        Args:
            variation_id: Variation ID
            language: Language code ('vi' or 'en')
        
        Returns:
            Formatted bonus text or empty string if no bonus
        """
        tiers = self.get_bonus_tiers_by_variation(variation_id, only_active=True)
        
        if not tiers:
            return ""
        
        # Get the first tier (smallest min_quantity) for display
        first_tier = tiers[0]
        
        if language == 'en':
            return f"(Buy {first_tier.min_quantity} get {first_tier.bonus_quantity} free)"
        else:
            return f"(Mua {first_tier.min_quantity} tặng {first_tier.bonus_quantity})"

    def get_all_bonus_tiers_for_variations(
        self,
        variation_ids: list[str],
        only_active: bool = True,
    ) -> dict[str, list[BonusTier]]:
        """
        Get bonus tiers for multiple variations in one query.
        
        Args:
            variation_ids: List of variation IDs
            only_active: If True, only return active tiers
        
        Returns:
            Dictionary mapping variation_id to list of BonusTier
        """
        query = self.session.query(BonusTier).filter(
            BonusTier.variation_id.in_(variation_ids)
        )
        
        if only_active:
            query = query.filter_by(is_active=True)
        
        tiers = query.order_by(BonusTier.min_quantity.asc()).all()
        
        # Group by variation_id
        result: dict[str, list[BonusTier]] = {vid: [] for vid in variation_ids}
        for tier in tiers:
            result[tier.variation_id].append(tier)
        
        return result
