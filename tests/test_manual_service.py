"""Tests for ManualService."""

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.dashboard.routers.manuals import ManualCreate
from src.database.models.base import Base
from src.database.models.enums import DeliveryType
from src.database.services.manual_service import ManualService
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
def sample_product(db_session):
    product_service = ProductService(db_session)
    return product_service.create_product(
        {
            "id": "prod_1",
            "name": "Test Product",
            "description": "",
            "delivery_type": DeliveryType.SUPPLIER_BASED,
            "is_active": True,
        }
    )


@pytest.fixture
def service(db_session):
    return ManualService(db_session)


class TestCreateManual:
    def test_create_manual_returns_correct_fields(self, service):
        manual = service.create_manual(
            {
                "title": "How to use",
                "content": "Step 1: Do this.",
                "is_active": True,
                "sort_order": 0,
            }
        )
        assert manual.id is not None
        assert manual.title == "How to use"
        assert manual.content == "Step 1: Do this."
        assert manual.is_active is True
        assert manual.sort_order == 0

    def test_create_manual_ignores_product_ids(self, service):
        manual = service.create_manual(
            {
                "title": "Guide",
                "content": "Content",
                "product_ids": ["p1", "p2"],
            }
        )
        assert manual.id is not None
        assert len(manual.product_assignments) == 0


class TestSetAssignments:
    def test_assign_and_unassign_products(self, service, sample_product, db_session):
        # Create a second product
        product_service = ProductService(db_session)
        product_service.create_product(
            {
                "id": "prod_2",
                "name": "Product 2",
                "description": "",
                "delivery_type": DeliveryType.SUPPLIER_BASED,
                "is_active": True,
            }
        )
        manual = service.create_manual({"title": "G", "content": "C"})
        service.set_assignments(manual.id, ["prod_1", "prod_2"])
        ids = service.get_assigned_product_ids(manual.id)
        assert set(ids) == {"prod_1", "prod_2"}

        # Reassign to only prod_2
        service.set_assignments(manual.id, ["prod_2"])
        ids = service.get_assigned_product_ids(manual.id)
        assert ids == ["prod_2"]

    def test_clear_assignments(self, service, sample_product):
        manual = service.create_manual({"title": "G", "content": "C"})
        service.set_assignments(manual.id, ["prod_1"])
        service.set_assignments(manual.id, [])
        ids = service.get_assigned_product_ids(manual.id)
        assert ids == []


class TestListManualsByProduct:
    def test_ordering_by_sort_order(self, service, sample_product):
        m1 = service.create_manual({"title": "C", "content": "x", "sort_order": 2})
        m2 = service.create_manual({"title": "A", "content": "x", "sort_order": 1})
        m3 = service.create_manual({"title": "B", "content": "x", "sort_order": 1})
        for m in [m1, m2, m3]:
            service.set_assignments(m.id, ["prod_1"])
        result = service.list_manuals_by_product("prod_1")
        # sort_order 1 first, then sort_order 2 (m1) last
        assert result[-1].id == m1.id
        assert result[0].sort_order <= result[-1].sort_order

    def test_only_active_filter(self, service, sample_product):
        active = service.create_manual(
            {"title": "Active", "content": "x", "is_active": True}
        )
        inactive = service.create_manual(
            {"title": "Inactive", "content": "x", "is_active": False}
        )
        for m in [active, inactive]:
            service.set_assignments(m.id, ["prod_1"])
        result = service.list_manuals_by_product("prod_1", only_active=True)
        ids = [m.id for m in result]
        assert active.id in ids
        assert inactive.id not in ids

    def test_inactive_included_when_flag_false(self, service, sample_product):
        active = service.create_manual(
            {"title": "Active", "content": "x", "is_active": True}
        )
        inactive = service.create_manual(
            {"title": "Inactive", "content": "x", "is_active": False}
        )
        for m in [active, inactive]:
            service.set_assignments(m.id, ["prod_1"])
        result = service.list_manuals_by_product("prod_1", only_active=False)
        ids = [m.id for m in result]
        assert active.id in ids
        assert inactive.id in ids


class TestManualCreateValidation:
    def test_content_over_4000_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ManualCreate(title="x", content="x" * 4001)

    def test_content_at_4000_is_valid(self):
        m = ManualCreate(title="x", content="x" * 4000)
        assert len(m.content) == 4000
