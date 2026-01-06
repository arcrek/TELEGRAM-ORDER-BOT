"""
Tests for product variation service layer.
Following TDD: Write tests first, then implement service.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models import DeliveryType
from src.database.services.variation_service import VariationService
from src.database.services.product_service import ProductService


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_product(db_session):
    """Create a sample product for testing."""
    product_service = ProductService(db_session)
    return product_service.create_product({
        "id": "prod_1",
        "name": "Test Product",
        "description": "Test description",
        "delivery_type": DeliveryType.PRE_UPLOADED,
        "is_active": True,
    })


@pytest.fixture
def variation_service(db_session):
    """Create variation service instance."""
    return VariationService(db_session)


class TestVariationService:
    """Test VariationService class."""

    def test_create_variation(self, variation_service, sample_product):
        """Test creating a product variation."""
        variation_data = {
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Pro 12M 1PCS",
            "price": 40000,
            "stock": 51,
            "is_active": True,
        }
        
        variation = variation_service.create_variation(variation_data)
        
        assert variation is not None
        assert variation.id == "var_1"
        assert variation.product_id == "prod_1"
        assert variation.name == "Pro 12M 1PCS"
        assert variation.price == 40000
        assert variation.stock == 51

    def test_get_variation_by_id(self, variation_service, sample_product):
        """Test retrieving a variation by ID."""
        variation_data = {
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Pro 12M 1PCS",
            "price": 40000,
            "stock": 51,
            "is_active": True,
        }
        variation_service.create_variation(variation_data)
        
        retrieved = variation_service.get_variation_by_id("var_1")
        
        assert retrieved is not None
        assert retrieved.id == "var_1"
        assert retrieved.name == "Pro 12M 1PCS"

    def test_list_variations_by_product(self, variation_service, sample_product):
        """Test listing variations for a product."""
        # Create multiple variations
        for i in range(3):
            variation_service.create_variation({
                "id": f"var_{i}",
                "product_id": "prod_1",
                "name": f"Variation {i}",
                "price": 10000 * (i + 1),
                "stock": 10 * (i + 1),
                "is_active": True,
            })
        
        variations = variation_service.list_variations_by_product("prod_1")
        
        assert len(variations) == 3
        assert all(v.product_id == "prod_1" for v in variations)

    def test_update_variation(self, variation_service, sample_product):
        """Test updating a variation."""
        variation_data = {
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Original Name",
            "price": 40000,
            "stock": 51,
            "is_active": True,
        }
        variation_service.create_variation(variation_data)
        
        update_data = {
            "name": "Updated Name",
            "price": 50000,
        }
        updated = variation_service.update_variation("var_1", update_data)
        
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.price == 50000
        assert updated.stock == 51  # Stock should not change unless explicitly updated

    def test_update_stock(self, variation_service, sample_product):
        """Test updating stock."""
        variation_data = {
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Pro 12M 1PCS",
            "price": 40000,
            "stock": 51,
            "is_active": True,
        }
        variation_service.create_variation(variation_data)
        
        # Increase stock
        updated = variation_service.update_stock("var_1", 100)
        assert updated.stock == 100
        
        # Decrease stock
        updated = variation_service.update_stock("var_1", 50)
        assert updated.stock == 50

    def test_decrease_stock(self, variation_service, sample_product):
        """Test decreasing stock (for orders)."""
        variation_data = {
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Pro 12M 1PCS",
            "price": 40000,
            "stock": 100,
            "is_active": True,
        }
        variation_service.create_variation(variation_data)
        
        # For PRE_UPLOADED products, decrease_stock validates from pre-uploaded products
        # but doesn't modify the stock field. Stock reduction happens when
        # pre-uploaded products are marked as used.
        # Since no pre-uploaded products exist, this will raise ValueError
        with pytest.raises(ValueError, match="Insufficient stock"):
            variation_service.decrease_stock("var_1", 5)

    def test_decrease_stock_insufficient(self, variation_service, sample_product):
        """Test decreasing stock when insufficient."""
        variation_data = {
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Pro 12M 1PCS",
            "price": 40000,
            "stock": 10,
            "is_active": True,
        }
        variation_service.create_variation(variation_data)
        
        # Try to decrease by more than available
        with pytest.raises(ValueError, match="Insufficient stock"):
            variation_service.decrease_stock("var_1", 20)

    def test_delete_variation_hard_delete(self, variation_service, sample_product):
        """Test hard deleting a variation."""
        variation_data = {
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Pro 12M 1PCS",
            "price": 40000,
            "stock": 51,
            "is_active": True,
        }
        variation_service.create_variation(variation_data)
        
        # Hard delete it
        result = variation_service.delete_variation("var_1")
        assert result is True
        
        # Variation should be completely removed
        deleted = variation_service.get_variation_by_id("var_1")
        assert deleted is None

