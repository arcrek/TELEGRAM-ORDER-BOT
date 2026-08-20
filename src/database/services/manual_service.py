"""Manual (user guide) service layer."""

import uuid

from sqlalchemy.orm import Session

from src.database.models.manual import Manual, ManualProductAssignment


class ManualService:
    """Service for managing user-guide manuals."""

    def __init__(self, session: Session):
        self.session = session

    def create_manual(self, data: dict) -> Manual:
        """Create a new manual. Ignores 'product_ids' key if present."""
        clean = {k: v for k, v in data.items() if k != "product_ids"}
        manual_id = clean.pop("id", None) or str(uuid.uuid4())
        manual = Manual(id=manual_id, **clean)
        self.session.add(manual)
        self.session.commit()
        self.session.refresh(manual)
        return manual

    def get_manual_by_id(self, manual_id: str) -> Manual | None:
        return self.session.query(Manual).filter_by(id=manual_id).first()

    def list_manuals(self, only_active: bool | None = None) -> list[Manual]:
        query = self.session.query(Manual)
        if only_active is not None:
            query = query.filter(Manual.is_active == only_active)
        return query.order_by(Manual.sort_order.asc(), Manual.created_at.asc()).all()

    def update_manual(self, manual_id: str, data: dict) -> Manual | None:
        """Update manual fields. Ignores 'product_ids' key."""
        manual = self.get_manual_by_id(manual_id)
        if not manual:
            return None
        allowed = {"title", "content", "is_active", "sort_order"}
        for field, value in data.items():
            if field in allowed and value is not None:
                setattr(manual, field, value)
        self.session.commit()
        self.session.refresh(manual)
        return manual

    def delete_manual(self, manual_id: str) -> bool:
        manual = self.get_manual_by_id(manual_id)
        if not manual:
            return False
        self.session.delete(manual)
        self.session.commit()
        return True

    def list_manuals_by_product(
        self, product_id: str, only_active: bool = True
    ) -> list[Manual]:
        """List manuals assigned to a product, ordered by sort_order then created_at."""
        query = (
            self.session.query(Manual)
            .join(
                ManualProductAssignment, Manual.id == ManualProductAssignment.manual_id
            )
            .filter(ManualProductAssignment.product_id == product_id)
        )
        if only_active:
            query = query.filter(Manual.is_active == True)
        return query.order_by(Manual.sort_order.asc(), Manual.created_at.asc()).all()

    def set_assignments(self, manual_id: str, product_ids: list[str]) -> None:
        """Replace all product assignments for a manual with the given list."""
        self.session.query(ManualProductAssignment).filter_by(
            manual_id=manual_id
        ).delete()
        for product_id in product_ids:
            assignment = ManualProductAssignment(
                id=str(uuid.uuid4()),
                manual_id=manual_id,
                product_id=product_id,
            )
            self.session.add(assignment)
        self.session.commit()

    def get_assigned_product_ids(self, manual_id: str) -> list[str]:
        rows = (
            self.session.query(ManualProductAssignment.product_id)
            .filter_by(manual_id=manual_id)
            .all()
        )
        return [r.product_id for r in rows]
