"""
Discount tier service for managing quantity-based price discounts.
"""
import uuid
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from src.database.models.discount_tier import DiscountTier
from src.database.models.product_variation import ProductVariation

VALID_DISCOUNT_TYPES = ('percentage', 'fixed_price')


class DiscountTierService:
    """Service for managing discount tiers."""

    def __init__(self, session: Session):
        self.session = session

    def create_discount_tier(
        self,
        variation_id: str,
        min_quantity: int,
        discount_type: str,
        discount_value: int,
        is_active: bool = True,
        tier_id: Optional[str] = None,
    ) -> DiscountTier:
        """
        Create a new discount tier.

        Raises:
            ValueError: If variation not found, duplicate min_quantity, or invalid inputs.
        """
        if discount_type not in VALID_DISCOUNT_TYPES:
            raise ValueError(f"discount_type must be one of {VALID_DISCOUNT_TYPES}")

        variation = self.session.query(ProductVariation).filter_by(id=variation_id).first()
        if not variation:
            raise ValueError(f"Variation {variation_id} not found")

        if discount_type == 'percentage' and not (0 < discount_value <= 100):
            raise ValueError("For percentage discount, discount_value must be 1-100")

        if discount_type == 'fixed_price' and discount_value <= 0:
            raise ValueError("For fixed_price discount, discount_value must be > 0")

        existing = self.session.query(DiscountTier).filter_by(
            variation_id=variation_id,
            min_quantity=min_quantity,
        ).first()
        if existing:
            raise ValueError(
                f"Discount tier with min_quantity {min_quantity} already exists for this variation"
            )

        if not tier_id:
            tier_id = f"disc_{uuid.uuid4().hex[:12]}"

        tier = DiscountTier(
            id=tier_id,
            variation_id=variation_id,
            min_quantity=min_quantity,
            discount_type=discount_type,
            discount_value=discount_value,
            is_active=is_active,
        )
        self.session.add(tier)
        self.session.commit()
        self.session.refresh(tier)
        return tier

    def get_discount_tier_by_id(self, tier_id: str) -> Optional[DiscountTier]:
        return self.session.query(DiscountTier).filter_by(id=tier_id).first()

    def get_discount_tiers_by_variation(
        self,
        variation_id: str,
        only_active: bool = True,
    ) -> List[DiscountTier]:
        query = self.session.query(DiscountTier).filter_by(variation_id=variation_id)
        if only_active:
            query = query.filter_by(is_active=True)
        return query.order_by(DiscountTier.min_quantity.asc()).all()

    def update_discount_tier(
        self,
        tier_id: str,
        update_data: Dict[str, Any],
    ) -> Optional[DiscountTier]:
        """
        Update a discount tier.

        Raises:
            ValueError: On duplicate min_quantity or invalid discount values.
        """
        tier = self.get_discount_tier_by_id(tier_id)
        if not tier:
            return None

        if 'min_quantity' in update_data:
            new_min = update_data['min_quantity']
            existing = self.session.query(DiscountTier).filter(
                DiscountTier.variation_id == tier.variation_id,
                DiscountTier.min_quantity == new_min,
                DiscountTier.id != tier_id,
            ).first()
            if existing:
                raise ValueError(
                    f"Discount tier with min_quantity {new_min} already exists for this variation"
                )

        new_type = update_data.get('discount_type', tier.discount_type)
        new_value = update_data.get('discount_value', tier.discount_value)

        if new_type not in VALID_DISCOUNT_TYPES:
            raise ValueError(f"discount_type must be one of {VALID_DISCOUNT_TYPES}")
        if new_type == 'percentage' and not (0 < new_value <= 100):
            raise ValueError("For percentage discount, discount_value must be 1-100")
        if new_type == 'fixed_price' and new_value <= 0:
            raise ValueError("For fixed_price discount, discount_value must be > 0")

        allowed_fields = ['min_quantity', 'discount_type', 'discount_value', 'is_active']
        for field, value in update_data.items():
            if field in allowed_fields and value is not None:
                setattr(tier, field, value)

        self.session.commit()
        self.session.refresh(tier)
        return tier

    def delete_discount_tier(self, tier_id: str) -> bool:
        tier = self.get_discount_tier_by_id(tier_id)
        if not tier:
            return False
        self.session.delete(tier)
        self.session.commit()
        return True

    def get_applicable_discount(
        self,
        variation_id: str,
        quantity: int,
    ) -> Optional[DiscountTier]:
        """
        Return the best (highest min_quantity) active tier where quantity >= min_quantity.
        No stock check needed — discounts don't consume extra stock.
        """
        tiers = self.get_discount_tiers_by_variation(variation_id, only_active=True)
        if not tiers:
            return None

        for tier in sorted(tiers, key=lambda t: t.min_quantity, reverse=True):
            if quantity >= tier.min_quantity:
                return tier

        return None

    def calculate_discounted_total(
        self,
        unit_price: int,
        quantity: int,
        tier: DiscountTier,
    ) -> Tuple[int, int]:
        """
        Calculate the post-discount subtotal and the savings amount.

        Returns:
            (total, discount_amount) both in VND
        """
        original = unit_price * quantity

        if tier.discount_type == 'percentage':
            total = round(original * (1 - tier.discount_value / 100))
        else:  # fixed_price
            total = tier.discount_value * quantity

        discount_amount = original - total
        return total, discount_amount

    def get_all_discount_tiers_for_variations(
        self,
        variation_ids: List[str],
        only_active: bool = True,
    ) -> Dict[str, List[DiscountTier]]:
        """Batch-fetch discount tiers for multiple variations."""
        query = self.session.query(DiscountTier).filter(
            DiscountTier.variation_id.in_(variation_ids)
        )
        if only_active:
            query = query.filter_by(is_active=True)

        tiers = query.order_by(DiscountTier.min_quantity.asc()).all()

        result: Dict[str, List[DiscountTier]] = {vid: [] for vid in variation_ids}
        for tier in tiers:
            result[tier.variation_id].append(tier)
        return result

    def format_discount_display(
        self,
        variation_id: str,
        language: str = 'vi',
    ) -> str:
        """
        Return a short display string for the first (lowest threshold) active discount tier.
        e.g. "(Mua 10+ giảm 5%)" or "(Buy 10+ at 10,000đ each)"
        """
        tiers = self.get_discount_tiers_by_variation(variation_id, only_active=True)
        if not tiers:
            return ""

        first = tiers[0]
        if first.discount_type == 'percentage':
            if language == 'en':
                return f"(Buy {first.min_quantity}+ get {first.discount_value}% off)"
            return f"(Mua {first.min_quantity}+ giảm {first.discount_value}%)"
        else:  # fixed_price
            if language == 'en':
                return f"(Buy {first.min_quantity}+ at {first.discount_value:,}đ each)"
            return f"(Mua {first.min_quantity}+ còn {first.discount_value:,}đ/tài khoản)"
