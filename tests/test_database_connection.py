"""
Tests for database connection setup.
"""
from src.database.connection import (
    get_database_url,
    create_engine_instance,
    get_session_factory,
    init_database,
    get_db_session,
)
from src.database.models import Product, DeliveryType


class TestDatabaseConnection:
    """Test database connection functions."""

    def test_get_database_url_default(self):
        """Test getting default database URL."""
    url = get_database_url()
    assert url == "sqlite:///data/database.db"

    def test_get_database_url_from_env(self, monkeypatch):
        """Test getting database URL from environment variable."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        url = get_database_url()
        assert url == "sqlite:///./test.db"

    def test_create_engine_instance(self):
        """Test creating engine instance."""
        engine = create_engine_instance("sqlite:///:memory:")
        assert engine is not None

    def test_get_session_factory(self):
        """Test getting session factory."""
        factory = get_session_factory()
        assert factory is not None
        session = factory()
        assert session is not None
        session.close()

    def test_init_database(self):
        """Test initializing database tables."""
        engine = create_engine_instance("sqlite:///:memory:")
        init_database(engine)
        
        # Verify tables are created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "products" in tables
        assert "orders" in tables
        assert "product_variations" in tables

    def test_get_db_session(self):
        """Test getting database session."""
        engine = create_engine_instance("sqlite:///:memory:")
        init_database(engine)
        
        session_gen = get_db_session(engine)
        session = next(session_gen)
        assert session is not None
        
        # Test that we can use the session
        product = Product(
            id="test_1",
            name="Test Product",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
        session.add(product)
        session.commit()
        
        retrieved = session.query(Product).filter_by(id="test_1").first()
        assert retrieved is not None
        assert retrieved.name == "Test Product"
        
        # Close session
        try:
            next(session_gen)
        except StopIteration:
            pass

