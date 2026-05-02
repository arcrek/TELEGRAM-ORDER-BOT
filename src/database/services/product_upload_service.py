"""
Product upload service layer for parsing and importing product data.
"""
import uuid
import csv
import io
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.models.pre_uploaded_product import PreUploadedProduct


class ProductUploadService:
    """Service for product upload operations."""
    
    def __init__(self, session: Session):
        """
        Initialize product upload service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    def parse_text_content(
        self, 
        content: str, 
        format_type: str = "line_separated"
    ) -> List[Dict[str, Any]]:
        """
        Parse text content based on format type.
        
        Args:
            content: Text content to parse
            format_type: Format type (line_separated, key_value, csv)
        
        Returns:
            List of parsed product data dictionaries
        """
        if format_type == "line_separated":
            return self._parse_line_separated(content)
        elif format_type == "key_value":
            return self._parse_key_value(content)
        elif format_type == "csv":
            return self._parse_csv(content)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")
    
    def _parse_line_separated(self, content: str) -> List[Dict[str, Any]]:
        """Parse line-separated format."""
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        return [{"data": line} for line in lines]
    
    def _parse_key_value(self, content: str) -> List[Dict[str, Any]]:
        """Parse key-value pairs format."""
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        result = []
        current_item = {}
        
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                # If we see a "name" key, start a new item
                if key.lower() == "name" and current_item:
                    result.append(current_item)
                    current_item = {}
                
                current_item[key.lower()] = value
            elif current_item:
                # Empty line or non-key-value line, finish current item
                result.append(current_item)
                current_item = {}
        
        if current_item:
            result.append(current_item)
        
        return result
    
    def _parse_csv(self, content: str) -> List[Dict[str, Any]]:
        """Parse CSV format."""
        reader = csv.DictReader(io.StringIO(content))
        return [dict(row) for row in reader]
    
    def validate_product_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate product data.
        
        Args:
            data: Product data dictionary
        
        Returns:
            True if valid, False otherwise
        """
        required_fields = ["product_id", "variation_id", "product_data"]
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                return False
        
        # Check if product exists
        product = self.session.query(Product).filter_by(id=data["product_id"]).first()
        if not product:
            return False
        
        # Check if variation exists
        variation = (
            self.session.query(ProductVariation)
            .filter_by(id=data["variation_id"], product_id=data["product_id"])
            .first()
        )
        if not variation:
            return False
        
        return True
    
    def _normalize_product_data_str(self, product_data: Any) -> str:
        """Return the canonical JSON string for a product_data value (same logic as bulk_import)."""
        if isinstance(product_data, dict):
            return json.dumps(product_data, ensure_ascii=False)
        if isinstance(product_data, str):
            try:
                parsed = json.loads(product_data)
                return json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                return json.dumps({"value": product_data}, ensure_ascii=False)
        return json.dumps({"value": str(product_data)}, ensure_ascii=False)

    def check_duplicates(
        self,
        products_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Check for duplicate product_data entries in the database.

        A duplicate is any (available or sold) PreUploadedProduct row for the
        same (variation_id, product_data) pair.

        Returns a dict with:
          - "duplicates": list of {"index": int, "data": ...} for each incoming
            item that already exists in the DB.
          - "duplicate_indices": set of indices that are duplicates.
          - "unique_count": number of non-duplicate items.
        """
        duplicate_entries = []
        duplicate_indices = set()

        for idx, data in enumerate(products_data):
            variation_id = data.get("variation_id")
            raw_product_data = data.get("product_data")
            if not variation_id or raw_product_data is None:
                continue

            normalized = self._normalize_product_data_str(raw_product_data)

            existing = (
                self.session.query(PreUploadedProduct)
                .filter_by(variation_id=variation_id, product_data=normalized)
                .first()
            )
            if existing:
                duplicate_entries.append({"index": idx, "data": data})
                duplicate_indices.add(idx)

        return {
            "duplicates": duplicate_entries,
            "duplicate_indices": duplicate_indices,
            "unique_count": len(products_data) - len(duplicate_indices),
        }

    def bulk_import_products(
        self,
        products_data: List[Dict[str, Any]],
        skip_duplicates: bool = False,
    ) -> Dict[str, Any]:
        """
        Bulk import products.
        
        Args:
            products_data: List of product data dictionaries
        
        Returns:
            Dictionary with import results
        """
        success_count = 0
        failed_count = 0
        duplicates_skipped = 0
        errors = []

        dup_result = self.check_duplicates(products_data)
        duplicate_indices = dup_result["duplicate_indices"]

        for idx, data in enumerate(products_data):
            try:
                if idx in duplicate_indices:
                    failed_count += 1
                    errors.append({
                        "index": idx,
                        "error": "Duplicate: product data already exists in database (available or sold)",
                        "data": data,
                    })
                    continue

                if not self.validate_product_data(data):
                    failed_count += 1
                    errors.append({
                        "index": idx,
                        "error": "Validation failed",
                        "data": data
                    })
                    continue

                product_data_str = self._normalize_product_data_str(data["product_data"])

                # Create pre-uploaded product
                pre_uploaded = PreUploadedProduct(
                    id=f"pre_{uuid.uuid4().hex[:8]}",
                    product_id=data["product_id"],
                    variation_id=data["variation_id"],
                    product_data=product_data_str,
                    is_used=False,
                )

                self.session.add(pre_uploaded)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "index": idx,
                    "error": str(e),
                    "data": data
                })

        self.session.commit()

        return {
            "success": success_count,
            "failed": failed_count,
            "duplicates_skipped": duplicates_skipped,
            "errors": errors,
        }
    
    def detect_format(self, content: str) -> str:
        """
        Auto-detect format type from content.
        
        Args:
            content: Text content
        
        Returns:
            Detected format type
        """
        lines = content.strip().split("\n")
        
        # Check for CSV (has comma-separated values in first line)
        if len(lines) > 0 and "," in lines[0]:
            return "csv"
        
        # Check for key-value pairs (has colon)
        if any(":" in line for line in lines[:5]):
            return "key_value"
        
        # Default to line-separated
        return "line_separated"

