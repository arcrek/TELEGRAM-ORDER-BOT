"""
Tests for product service layer.
Following TDD: Write tests first, then implement service.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import DeliveryType
from src.database.models.base import Base
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
def product_service(db_session):
    """Create product service instance."""
    return ProductService(db_session)


class TestProductService:
    """Test ProductService class."""

    def test_create_product(self, product_service):
        """Test creating a product."""
        product_data = {
            "id": "prod_1",
            "name": "Test Product",
            "description": "Test description",
            "delivery_type": DeliveryType.PRE_UPLOADED,
            "is_active": True,
        }
        
        product = product_service.create_product(product_data)
        
        assert product is not None
        assert product.id == "prod_1"
        assert product.name == "Test Product"
        assert product.description == "Test description"
        assert product.delivery_type == DeliveryType.PRE_UPLOADED
        assert product.is_active is True

    def test_virtual_order_delivery_content_is_editable(self, product_service):
        product = product_service.create_product({
            "id": "prod_virtual",
            "name": "Đơn ảo",
            "delivery_type": DeliveryType.VIRTUAL_ORDER,
            "upgrade_request_text": "Liên hệ hỗ trợ: @old",
        })
        updated = product_service.update_product(product.id, {
            "upgrade_request_text": "Liên hệ hỗ trợ: @new",
        })

        assert updated.upgrade_request_text == "Liên hệ hỗ trợ: @new"
        with pytest.raises(ValueError, match="delivery content is required"):
            product_service.update_product(product.id, {"upgrade_request_text": ""})

    def test_get_product_by_id(self, product_service):
        """Test retrieving a product by ID."""
        # Create a product first
        product_data = {
            "id": "prod_1",
            "name": "Test Product",
            "description": "Test description",
            "delivery_type": DeliveryType.PRE_UPLOADED,
            "is_active": True,
        }
        product_service.create_product(product_data)
        
        # Retrieve it
        retrieved = product_service.get_product_by_id("prod_1")
        
        assert retrieved is not None
        assert retrieved.id == "prod_1"
        assert retrieved.name == "Test Product"

    def test_get_product_by_id_not_found(self, product_service):
        """Test retrieving a non-existent product."""
        retrieved = product_service.get_product_by_id("nonexistent")
        assert retrieved is None

    def test_list_products_paginated(self, product_service):
        """Test listing products with pagination."""
        # Create multiple products
        # Use zero-padded names to ensure correct lexicographic ordering
        for i in range(20):
            product_data = {
                "id": f"prod_{i:02d}",
                "name": f"Product {i:02d}",
                "description": f"Description {i}",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "is_active": True,
            }
            product_service.create_product(product_data)
        
        # Get first page (15 items per page)
        page1 = product_service.list_products(page=1, per_page=15)
        
        assert len(page1) == 15
        assert page1[0].id == "prod_00"
        assert page1[14].id == "prod_14"
        
        # Get second page
        page2 = product_service.list_products(page=2, per_page=15)
        assert len(page2) == 5
        assert page2[0].id == "prod_15"

    def test_list_products_only_active(self, product_service):
        """Test listing only active products."""
        # Create active and inactive products
        product_service.create_product({
            "id": "prod_active",
            "name": "Active Product",
            "delivery_type": DeliveryType.PRE_UPLOADED,
            "is_active": True,
        })
        product_service.create_product({
            "id": "prod_inactive",
            "name": "Inactive Product",
            "delivery_type": DeliveryType.PRE_UPLOADED,
            "is_active": False,
        })
        
        active_products = product_service.list_products(only_active=True)
        
        assert len(active_products) == 1
        assert active_products[0].id == "prod_active"

    def test_update_product(self, product_service):
        """Test updating a product."""
        # Create a product
        product_data = {
            "id": "prod_1",
            "name": "Original Name",
            "description": "Original description",
            "delivery_type": DeliveryType.PRE_UPLOADED,
            "is_active": True,
        }
        product_service.create_product(product_data)
        
        # Update it
        update_data = {
            "name": "Updated Name",
            "description": "Updated description",
        }
        updated = product_service.update_product("prod_1", update_data)
        
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.id == "prod_1"  # ID should not change

    def test_delete_product_hard_delete(self, product_service):
        """Test hard deleting a product."""
        # Create a product
        product_data = {
            "id": "prod_1",
            "name": "Test Product",
            "delivery_type": DeliveryType.PRE_UPLOADED,
            "is_active": True,
        }
        product_service.create_product(product_data)
        
        # Hard delete it
        result = product_service.delete_product("prod_1")
        assert result is True
        
        # Product should be completely removed
        deleted = product_service.get_product_by_id("prod_1")
        assert deleted is None
        
        # Should not appear in any list
        active_products = product_service.list_products(only_active=True)
        assert len(active_products) == 0

    def test_get_total_products_count(self, product_service):
        """Test getting total products count."""
        # Create multiple products
        for i in range(10):
            product_service.create_product({
                "id": f"prod_{i}",
                "name": f"Product {i}",
                "delivery_type": DeliveryType.PRE_UPLOADED,
                "is_active": True,
            })
        
        count = product_service.get_total_count(only_active=True)
        assert count == 10
