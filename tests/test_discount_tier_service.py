"""
Tests for DiscountTierService.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models import DeliveryType
from src.database.services.discount_tier_service import DiscountTierService
from src.database.services.variation_service import VariationService
from src.database.services.product_service import ProductService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_variation(db_session):
    product_service = ProductService(db_session)
    product_service.create_product({
        "id": "prod_1",
        "name": "Test Product",
        "description": "",
        "delivery_type": DeliveryType.SUPPLIER_BASED,
        "is_active": True,
    })
    variation_service = VariationService(db_session)
    return variation_service.create_variation({
        "id": "var_1",
        "product_id": "prod_1",
        "name": "Pro 12M",
        "price": 15000,
        "stock": 100,
        "is_active": True,
    })


@pytest.fixture
def service(db_session):
    return DiscountTierService(db_session)


class TestCalculateDiscountedTotal:
    def test_percentage_discount(self, service, sample_variation):
        tier = service.create_discount_tier(
            variation_id="var_1",
            min_quantity=10,
            discount_type="percentage",
            discount_value=5,
        )
        total, discount_amount = service.calculate_discounted_total(15000, 10, tier)
        assert total == round(15000 * 10 * 0.95)
        assert discount_amount == 15000 * 10 - total

    def test_fixed_price_discount(self, service, sample_variation):
        tier = service.create_discount_tier(
            variation_id="var_1",
            min_quantity=10,
            discount_type="fixed_price",
            discount_value=10000,
        )
        total, discount_amount = service.calculate_discounted_total(15000, 10, tier)
        assert total == 10000 * 10
        assert discount_amount == (15000 - 10000) * 10

    def test_zero_discount_on_no_tier(self, service, sample_variation):
        tier = service.get_applicable_discount("var_1", 5)
        assert tier is None


class TestGetApplicableDiscount:
    def test_returns_best_tier(self, service, sample_variation):
        service.create_discount_tier("var_1", 5, "percentage", 3)
        service.create_discount_tier("var_1", 10, "percentage", 5)
        service.create_discount_tier("var_1", 20, "percentage", 10)

        tier = service.get_applicable_discount("var_1", 15)
        assert tier is not None
        assert tier.min_quantity == 10  # best fitting — 20 > 15

    def test_returns_highest_qualifying_tier(self, service, sample_variation):
        service.create_discount_tier("var_1", 5, "percentage", 3)
        service.create_discount_tier("var_1", 20, "percentage", 10)

        tier = service.get_applicable_discount("var_1", 25)
        assert tier.min_quantity == 20

    def test_no_tier_when_below_threshold(self, service, sample_variation):
        service.create_discount_tier("var_1", 10, "percentage", 5)
        tier = service.get_applicable_discount("var_1", 9)
        assert tier is None

    def test_inactive_tier_ignored(self, service, sample_variation):
        service.create_discount_tier("var_1", 5, "percentage", 5, is_active=False)
        tier = service.get_applicable_discount("var_1", 10)
        assert tier is None


class TestCreateDiscountTier:
    def test_invalid_type_raises(self, service, sample_variation):
        with pytest.raises(ValueError, match="discount_type"):
            service.create_discount_tier("var_1", 10, "invalid", 5)

    def test_percentage_over_100_raises(self, service, sample_variation):
        with pytest.raises(ValueError):
            service.create_discount_tier("var_1", 10, "percentage", 101)

    def test_fixed_price_zero_raises(self, service, sample_variation):
        with pytest.raises(ValueError):
            service.create_discount_tier("var_1", 10, "fixed_price", 0)

    def test_duplicate_min_quantity_raises(self, service, sample_variation):
        service.create_discount_tier("var_1", 10, "percentage", 5)
        with pytest.raises(ValueError, match="already exists"):
            service.create_discount_tier("var_1", 10, "percentage", 10)

    def test_nonexistent_variation_raises(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.create_discount_tier("nonexistent", 10, "percentage", 5)


class TestFormatDiscountDisplay:
    def test_percentage_vi(self, service, sample_variation):
        service.create_discount_tier("var_1", 10, "percentage", 5)
        text = service.format_discount_display("var_1", language="vi")
        assert "10" in text
        assert "5%" in text

    def test_fixed_price_en(self, service, sample_variation):
        service.create_discount_tier("var_1", 10, "fixed_price", 10000)
        text = service.format_discount_display("var_1", language="en")
        assert "10" in text
        assert "10,000" in text

    def test_no_tiers_returns_empty(self, service, sample_variation):
        assert service.format_discount_display("var_1") == ""
