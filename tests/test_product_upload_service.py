"""
Tests for product upload service.
Following TDD: Write tests first, then implement service.
"""
import pytest
from sqlalchemy.orm import Session

from src.database.connection import (
    create_engine_instance,
    get_session_factory,
    init_database,
)
from src.database.models import DeliveryType, Product, ProductVariation
from src.database.services.product_upload_service import ProductUploadService


@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine_instance("sqlite:///:memory:")
    init_database(engine)
    session_factory = get_session_factory(engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def sample_product(test_db: Session):
    """Create a sample product."""
    product = Product(
        id="prod_1",
        name="Test Product",
        description="Test Description",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    test_db.add(product)
    variation = ProductVariation(
        id="var_1",
        product_id="prod_1",
        name="Variation 1",
        price=100000,
        stock=10,
        is_active=True,
    )
    test_db.add(variation)
    test_db.commit()
    return product


class TestProductUploadService:
    """Test product upload service."""
    
    def test_parse_line_separated_format(self, test_db: Session):
        """Test parsing line-separated format."""
        service = ProductUploadService(test_db)
        content = "Product 1\nProduct 2\nProduct 3"
        result = service.parse_text_content(content, format_type="line_separated")
        assert len(result) == 3
        assert result[0]["data"] == "Product 1"
        assert result[1]["data"] == "Product 2"
        assert result[2]["data"] == "Product 3"
    
    def test_parse_key_value_format(self, test_db: Session):
        """Test parsing key-value pairs format."""
        service = ProductUploadService(test_db)
        content = "name: Product 1\nprice: 100000\nname: Product 2\nprice: 200000"
        result = service.parse_text_content(content, format_type="key_value")
        assert len(result) == 2
        assert result[0]["name"] == "Product 1"
        assert result[0]["price"] == "100000"
    
    def test_parse_csv_format(self, test_db: Session):
        """Test parsing CSV format."""
        service = ProductUploadService(test_db)
        content = "name,price,stock\nProduct 1,100000,10\nProduct 2,200000,20"
        result = service.parse_text_content(content, format_type="csv")
        assert len(result) == 2
        assert result[0]["name"] == "Product 1"
        assert result[0]["price"] == "100000"
        assert result[0]["stock"] == "10"
    
    def test_validate_product_data(self, test_db: Session, sample_product):
        """Test product data validation."""
        service = ProductUploadService(test_db)
        
        # Valid data
        valid_data = {
            "product_id": "prod_1",
            "variation_id": "var_1",
            "product_data": "test data"
        }
        assert service.validate_product_data(valid_data) is True
        
        # Invalid product_id
        invalid_data = {
            "product_id": "invalid",
            "variation_id": "var_1",
            "product_data": "test data"
        }
        assert service.validate_product_data(invalid_data) is False
    
    def test_bulk_import_products(self, test_db: Session, sample_product):
        """Test bulk importing products."""
        service = ProductUploadService(test_db)
        
        products_data = [
            {
                "product_id": "prod_1",
                "variation_id": "var_1",
                "product_data": "data1"
            },
            {
                "product_id": "prod_1",
                "variation_id": "var_1",
                "product_data": "data2"
            },
        ]
        
        result = service.bulk_import_products(products_data)
        assert result["success"] == 2
        assert result["failed"] == 0
        assert len(result["errors"]) == 0

