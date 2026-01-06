"""
Tests for product supplier assignment service layer.
Following TDD: Write tests first, then implement service.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models import DeliveryType
from src.database.services.product_supplier_assignment_service import ProductSupplierAssignmentService
from src.database.services.product_service import ProductService
from src.database.services.supplier_service import SupplierService


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
        "delivery_type": DeliveryType.SUPPLIER_BASED,
        "is_active": True,
    })


@pytest.fixture
def sample_supplier(db_session):
    """Create a sample supplier for testing."""
    supplier_service = SupplierService(db_session)
    return supplier_service.create_supplier(
        telegram_user_id=123456789,
        name="Test Supplier",
        is_active=True,
    )


@pytest.fixture
def assignment_service(db_session):
    """Create assignment service instance."""
    return ProductSupplierAssignmentService(db_session)


class TestProductSupplierAssignmentService:
    """Test ProductSupplierAssignmentService class."""

    def test_generate_assignment_id(self, assignment_service):
        """Test assignment ID generation."""
        assignment_id = assignment_service.generate_assignment_id()
        assert assignment_id.startswith("psa_")
        assert len(assignment_id) == 12  # "psa_" + 8 hex chars

    def test_create_assignment_success(self, assignment_service, sample_product, sample_supplier):
        """Test creating an assignment."""
        assignment = assignment_service.create_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
            is_primary=False,
        )
        
        assert assignment is not None
        assert assignment.product_id == sample_product.id
        assert assignment.supplier_id == sample_supplier.id
        assert assignment.is_primary is False

    def test_create_assignment_primary(self, assignment_service, sample_product, sample_supplier):
        """Test creating a primary assignment."""
        assignment = assignment_service.create_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
            is_primary=True,
        )
        
        assert assignment is not None
        assert assignment.is_primary is True

    def test_create_assignment_duplicate(self, assignment_service, sample_product, sample_supplier):
        """Test creating duplicate assignment fails."""
        assignment_service.create_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
        )
        
        # Try to create duplicate
        duplicate = assignment_service.create_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
        )
        
        assert duplicate is None

    def test_create_assignment_invalid_product(self, assignment_service, sample_supplier):
        """Test creating assignment with invalid product ID."""
        assignment = assignment_service.create_assignment(
            product_id="nonexistent",
            supplier_id=sample_supplier.id,
        )
        
        assert assignment is None

    def test_create_assignment_invalid_supplier(self, assignment_service, sample_product):
        """Test creating assignment with invalid supplier ID."""
        assignment = assignment_service.create_assignment(
            product_id=sample_product.id,
            supplier_id="nonexistent",
        )
        
        assert assignment is None

    def test_get_assignment_success(self, assignment_service, sample_product, sample_supplier):
        """Test getting an assignment."""
        assignment_service.create_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
        )
        
        assignment = assignment_service.get_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
        )
        
        assert assignment is not None
        assert assignment.product_id == sample_product.id
        assert assignment.supplier_id == sample_supplier.id

    def test_get_assignments_by_product(self, assignment_service, sample_product, db_session):
        """Test getting all assignments for a product."""
        # Create multiple suppliers
        supplier1 = SupplierService(db_session).create_supplier(111111111, "Supplier 1")
        supplier2 = SupplierService(db_session).create_supplier(222222222, "Supplier 2")
        
        assignment_service.create_assignment(sample_product.id, supplier1.id, is_primary=True)
        assignment_service.create_assignment(sample_product.id, supplier2.id, is_primary=False)
        
        assignments = assignment_service.get_assignments_by_product(sample_product.id)
        
        assert len(assignments) == 2
        # Primary should be first
        assert assignments[0].is_primary is True

    def test_get_assignments_by_supplier(self, assignment_service, sample_supplier, db_session):
        """Test getting all assignments for a supplier."""
        # Create multiple products
        product1 = ProductService(db_session).create_product({
            "id": "prod_1", "name": "Product 1", "delivery_type": DeliveryType.SUPPLIER_BASED, "is_active": True
        })
        product2 = ProductService(db_session).create_product({
            "id": "prod_2", "name": "Product 2", "delivery_type": DeliveryType.SUPPLIER_BASED, "is_active": True
        })
        
        assignment_service.create_assignment(product1.id, sample_supplier.id)
        assignment_service.create_assignment(product2.id, sample_supplier.id)
        
        assignments = assignment_service.get_assignments_by_supplier(sample_supplier.id)
        
        assert len(assignments) == 2

    def test_get_primary_supplier_for_product(self, assignment_service, sample_product, db_session):
        """Test getting primary supplier for a product."""
        supplier1 = SupplierService(db_session).create_supplier(111111111, "Supplier 1")
        supplier2 = SupplierService(db_session).create_supplier(222222222, "Supplier 2")
        
        assignment_service.create_assignment(sample_product.id, supplier1.id, is_primary=False)
        assignment_service.create_assignment(sample_product.id, supplier2.id, is_primary=True)
        
        primary = assignment_service.get_primary_supplier_for_product(sample_product.id)
        
        assert primary is not None
        assert primary.id == supplier2.id

    def test_update_assignment_primary(self, assignment_service, sample_product, db_session):
        """Test updating assignment to primary."""
        supplier1 = SupplierService(db_session).create_supplier(111111111, "Supplier 1")
        supplier2 = SupplierService(db_session).create_supplier(222222222, "Supplier 2")
        
        assignment_service.create_assignment(sample_product.id, supplier1.id, is_primary=True)
        assignment_service.create_assignment(sample_product.id, supplier2.id, is_primary=False)
        
        # Update supplier2 to primary (should unset supplier1)
        updated = assignment_service.update_assignment(
            sample_product.id,
            supplier2.id,
            is_primary=True,
        )
        
        assert updated is not None
        assert updated.is_primary is True
        
        # Verify supplier1 is no longer primary
        assignment1 = assignment_service.get_assignment(sample_product.id, supplier1.id)
        assert assignment1.is_primary is False

    def test_delete_assignment_success(self, assignment_service, sample_product, sample_supplier):
        """Test deleting an assignment."""
        assignment_service.create_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
        )
        
        success = assignment_service.delete_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
        )
        
        assert success is True
        
        # Verify it's deleted
        assignment = assignment_service.get_assignment(
            sample_product.id,
            sample_supplier.id,
        )
        assert assignment is None

    def test_delete_assignment_not_found(self, assignment_service, sample_product, sample_supplier):
        """Test deleting non-existent assignment."""
        success = assignment_service.delete_assignment(
            product_id=sample_product.id,
            supplier_id=sample_supplier.id,
        )
        
        assert success is False

    def test_get_products_by_supplier(self, assignment_service, sample_supplier, db_session):
        """Test getting products assigned to a supplier."""
        product1 = ProductService(db_session).create_product({
            "id": "prod_1", "name": "Product 1", "delivery_type": DeliveryType.SUPPLIER_BASED, "is_active": True
        })
        product2 = ProductService(db_session).create_product({
            "id": "prod_2", "name": "Product 2", "delivery_type": DeliveryType.SUPPLIER_BASED, "is_active": True
        })
        
        assignment_service.create_assignment(product1.id, sample_supplier.id, is_primary=True)
        assignment_service.create_assignment(product2.id, sample_supplier.id, is_primary=False)
        
        products = assignment_service.get_products_by_supplier(sample_supplier.id)
        
        assert len(products) == 2
        assert products[0]["is_primary"] is True
        assert products[0]["product_name"] == "Product 1"

    def test_get_suppliers_by_product(self, assignment_service, sample_product, db_session):
        """Test getting suppliers assigned to a product."""
        supplier1 = SupplierService(db_session).create_supplier(111111111, "Supplier 1")
        supplier2 = SupplierService(db_session).create_supplier(222222222, "Supplier 2")
        
        assignment_service.create_assignment(sample_product.id, supplier1.id, is_primary=True)
        assignment_service.create_assignment(sample_product.id, supplier2.id, is_primary=False)
        
        suppliers = assignment_service.get_suppliers_by_product(sample_product.id)
        
        assert len(suppliers) == 2
        assert suppliers[0]["is_primary"] is True
        assert suppliers[0]["supplier_name"] == "Supplier 1"

