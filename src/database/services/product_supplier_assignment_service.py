"""
Product supplier assignment service layer.
"""
import uuid
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from src.database.models.product_supplier_assignment import ProductSupplierAssignment
from src.database.models.product import Product
from src.database.models.supplier import Supplier


class ProductSupplierAssignmentService:
    """Service for product-supplier assignment operations."""

    def __init__(self, session: Session):
        """
        Initialize assignment service.
        
        Args:
            session: Database session
        """
        self.session = session

    def generate_assignment_id(self) -> str:
        """
        Generate a unique assignment ID.
        
        Returns:
            Assignment ID string
        """
        return f"psa_{uuid.uuid4().hex[:8]}"

    def create_assignment(
        self,
        product_id: str,
        supplier_id: str,
        is_primary: bool = False,
    ) -> Optional[ProductSupplierAssignment]:
        """
        Create a product-supplier assignment.
        
        Args:
            product_id: Product ID
            supplier_id: Supplier ID
            is_primary: Whether this is the primary supplier for the product
        
        Returns:
            Created assignment or None if product/supplier not found or already assigned
        """
        # Check if product exists
        product = self.session.query(Product).filter_by(id=product_id).first()
        if not product:
            return None
        
        # Check if supplier exists
        supplier = self.session.query(Supplier).filter_by(id=supplier_id).first()
        if not supplier:
            return None
        
        # Check if assignment already exists
        existing = (
            self.session.query(ProductSupplierAssignment)
            .filter_by(product_id=product_id, supplier_id=supplier_id)
            .first()
        )
        if existing:
            return None  # Already assigned
        
        # If setting as primary, unset other primary assignments for this product
        if is_primary:
            self.session.query(ProductSupplierAssignment).filter_by(
                product_id=product_id,
                is_primary=True
            ).update({"is_primary": False})
        
        assignment = ProductSupplierAssignment(
            id=self.generate_assignment_id(),
            product_id=product_id,
            supplier_id=supplier_id,
            is_primary=is_primary,
        )
        
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)
        
        return assignment

    def get_assignment(
        self,
        product_id: str,
        supplier_id: str,
    ) -> Optional[ProductSupplierAssignment]:
        """
        Get assignment by product and supplier IDs.
        
        Args:
            product_id: Product ID
            supplier_id: Supplier ID
        
        Returns:
            Assignment instance or None if not found
        """
        return (
            self.session.query(ProductSupplierAssignment)
            .filter_by(product_id=product_id, supplier_id=supplier_id)
            .first()
        )

    def get_assignments_by_product(self, product_id: str) -> List[ProductSupplierAssignment]:
        """
        Get all assignments for a product.
        
        Args:
            product_id: Product ID
        
        Returns:
            List of assignments
        """
        return (
            self.session.query(ProductSupplierAssignment)
            .filter_by(product_id=product_id)
            .order_by(ProductSupplierAssignment.is_primary.desc(), ProductSupplierAssignment.created_at)
            .all()
        )

    def get_assignments_by_supplier(self, supplier_id: str) -> List[ProductSupplierAssignment]:
        """
        Get all assignments for a supplier.
        
        Args:
            supplier_id: Supplier ID
        
        Returns:
            List of assignments
        """
        return (
            self.session.query(ProductSupplierAssignment)
            .filter_by(supplier_id=supplier_id)
            .order_by(ProductSupplierAssignment.is_primary.desc(), ProductSupplierAssignment.created_at)
            .all()
        )

    def get_primary_supplier_for_product(self, product_id: str) -> Optional[Supplier]:
        """
        Get the primary supplier for a product.
        
        Args:
            product_id: Product ID
        
        Returns:
            Supplier instance or None if not found
        """
        assignment = (
            self.session.query(ProductSupplierAssignment)
            .filter_by(product_id=product_id, is_primary=True)
            .first()
        )
        
        if assignment:
            return assignment.supplier
        return None

    def update_assignment(
        self,
        product_id: str,
        supplier_id: str,
        is_primary: Optional[bool] = None,
    ) -> Optional[ProductSupplierAssignment]:
        """
        Update an assignment.
        
        Args:
            product_id: Product ID
            supplier_id: Supplier ID
            is_primary: New primary status
        
        Returns:
            Updated assignment or None if not found
        """
        assignment = self.get_assignment(product_id, supplier_id)
        if not assignment:
            return None
        
        if is_primary is not None:
            # If setting as primary, unset other primary assignments for this product
            if is_primary:
                self.session.query(ProductSupplierAssignment).filter_by(
                    product_id=product_id,
                    is_primary=True
                ).update({"is_primary": False})
            
            assignment.is_primary = is_primary
        
        self.session.commit()
        self.session.refresh(assignment)
        
        return assignment

    def delete_assignment(
        self,
        product_id: str,
        supplier_id: str,
    ) -> bool:
        """
        Delete an assignment.
        
        Args:
            product_id: Product ID
            supplier_id: Supplier ID
        
        Returns:
            True if deleted, False if not found
        """
        assignment = self.get_assignment(product_id, supplier_id)
        if not assignment:
            return False
        
        self.session.delete(assignment)
        self.session.commit()
        
        return True

    def get_products_by_supplier(self, supplier_id: str) -> List[Dict]:
        """
        Get all products assigned to a supplier with product details.
        
        Args:
            supplier_id: Supplier ID
        
        Returns:
            List of dictionaries with product and assignment info
        """
        assignments = self.get_assignments_by_supplier(supplier_id)
        
        results = []
        for assignment in assignments:
            product = assignment.product
            if product:
                results.append({
                    "assignment_id": assignment.id,
                    "product_id": product.id,
                    "product_name": product.name,
                    "is_primary": assignment.is_primary,
                    "created_at": assignment.created_at.isoformat(),
                })
        
        return results

    def get_suppliers_by_product(self, product_id: str) -> List[Dict]:
        """
        Get all suppliers assigned to a product with supplier details.
        
        Args:
            product_id: Product ID
        
        Returns:
            List of dictionaries with supplier and assignment info
        """
        assignments = self.get_assignments_by_product(product_id)
        
        results = []
        for assignment in assignments:
            supplier = assignment.supplier
            if supplier:
                results.append({
                    "assignment_id": assignment.id,
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "telegram_user_id": supplier.telegram_user_id,
                    "is_primary": assignment.is_primary,
                    "is_active": supplier.is_active,
                    "created_at": assignment.created_at.isoformat(),
                })
        
        return results

