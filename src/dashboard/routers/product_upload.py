"""
Product upload router.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.dashboard.auth import get_current_admin, get_db
from src.database.services.product_upload_service import ProductUploadService


router = APIRouter()


class ParseTextRequest(BaseModel):
    """Parse text content request schema."""
    content: str
    format_type: str = "line_separated"  # line_separated, key_value, csv


class ParseTextResponse(BaseModel):
    """Parse text content response schema."""
    parsed_data: List[dict]
    format_type: str
    item_count: int


class ProductUploadItem(BaseModel):
    """Product upload item schema."""
    product_id: str
    variation_id: str
    product_data: str


class BulkUploadRequest(BaseModel):
    """Bulk upload request schema."""
    products: List[ProductUploadItem]


class BulkUploadResponse(BaseModel):
    """Bulk upload response schema."""
    success: int
    failed: int
    errors: List[dict]


@router.post("/products/upload/parse", response_model=ParseTextResponse)
async def parse_text_content(
    request: ParseTextRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Parse text content for product upload.
    
    Args:
        request: Parse request with content and format type
    
    Returns:
        Parsed data
    """
    service = ProductUploadService(db)
    
    try:
        parsed_data = service.parse_text_content(
            request.content,
            request.format_type
        )
        
        return {
            "parsed_data": parsed_data,
            "format_type": request.format_type,
            "item_count": len(parsed_data),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/products/upload", response_model=BulkUploadResponse)
async def upload_products(
    request: BulkUploadRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Bulk upload products.
    
    Args:
        request: Bulk upload request with products list
    
    Returns:
        Upload results
    """
    service = ProductUploadService(db)
    
    products_data = [
        {
            "product_id": p.product_id,
            "variation_id": p.variation_id,
            "product_data": p.product_data,
        }
        for p in request.products
    ]
    
    result = service.bulk_import_products(products_data)
    
    return {
        "success": result["success"],
        "failed": result["failed"],
        "errors": result["errors"],
    }


@router.post("/products/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    format_type: Optional[str] = None,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Upload products from file.
    
    Args:
        file: Uploaded file
        format_type: Format type (auto-detected if not provided)
    
    Returns:
        Upload results
    """
    # Validate file type
    if not file.filename.endswith('.txt'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt files are supported"
        )
    
    # Read file content
    content = await file.read()
    content_str = content.decode('utf-8')
    
    service = ProductUploadService(db)
    
    # Auto-detect format if not provided
    if not format_type:
        format_type = service.detect_format(content_str)
    
    # Parse content
    try:
        parsed_data = service.parse_text_content(content_str, format_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {str(e)}"
        )
    
    # For now, return parsed data
    # In a real implementation, you'd need to map parsed data to products
    return {
        "parsed_data": parsed_data,
        "format_type": format_type,
        "item_count": len(parsed_data),
        "message": "File parsed successfully. Please map fields to products."
    }

