"""
Statistics router.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.dashboard.auth import get_current_admin, get_db
from src.database.services.statistics_service import StatisticsService

router = APIRouter()


def _resolve_range(
    range_: Optional[str],
    from_: Optional[str],
    to_: Optional[str],
):
    """Resolve (start_date, end_date) from range shorthand or explicit ISO dates."""
    now = datetime.now(timezone.utc)
    if range_ == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if range_ == "7d":
        return now - timedelta(days=7), now
    if range_ == "30d":
        return now - timedelta(days=30), now
    if range_ == "90d":
        return now - timedelta(days=90), now
    if range_ == "custom":
        if not from_ or not to_:
            raise HTTPException(status_code=422, detail="from and to required for custom range")
        try:
            return datetime.fromisoformat(from_).replace(tzinfo=timezone.utc), \
                   datetime.fromisoformat(to_).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid date: {exc}") from exc
    return None, None


@router.get("/overview")
async def get_statistics_overview(
    range: Optional[str] = Query(None, description="Preset: today|7d|30d|90d|custom"),
    from_date: Optional[str] = Query(None, alias="from", description="ISO date for custom range"),
    to_date: Optional[str] = Query(None, alias="to", description="ISO date for custom range"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get comprehensive statistics overview with optional date range filter."""
    start_date, end_date = _resolve_range(range, from_date, to_date)
    service = StatisticsService(db)
    return service.get_statistics_overview(start_date=start_date, end_date=end_date)


@router.get("/orders/count")
async def get_orders_count(
    period: Optional[str] = Query(None, description="Period: today, this_week, this_month, or None for all time"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get total orders count.
    
    Args:
        period: Period filter (today, this_week, this_month, or None for all time)
    
    Returns:
        Total orders count
    """
    service = StatisticsService(db)
    count = service.get_total_orders_count(period=period)
    return {"count": count, "period": period or "all_time"}


@router.get("/revenue")
async def get_revenue(
    period: Optional[str] = Query(None, description="Period: today, this_week, this_month, or None for all time"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get total revenue.
    
    Args:
        period: Period filter (today, this_week, this_month, or None for all time)
    
    Returns:
        Total revenue in VND
    """
    service = StatisticsService(db)
    revenue = service.get_total_revenue(period=period)
    return {"revenue": revenue, "period": period or "all_time"}


@router.get("/orders/by-status")
async def get_orders_by_status(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get orders grouped by status.
    
    Returns:
        Dictionary mapping status to count
    """
    service = StatisticsService(db)
    return service.get_orders_by_status()


@router.get("/orders/by-product")
async def get_orders_by_product(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get orders grouped by product.
    
    Returns:
        List of dictionaries with product_id, product_name, and order_count
    """
    service = StatisticsService(db)
    return service.get_orders_by_product()


@router.get("/revenue/over-time")
async def get_revenue_over_time(
    interval: str = Query("daily", description="Interval: daily, weekly, or monthly"),
    days: int = Query(30, description="Number of days to look back"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get revenue over time.
    
    Args:
        interval: Time interval (daily, weekly, monthly)
        days: Number of days to look back
    
    Returns:
        List of dictionaries with date and revenue
    """
    service = StatisticsService(db)
    return service.get_revenue_over_time(interval=interval, days=days)


@router.get("/products/top-selling")
async def get_top_selling_products(
    limit: int = Query(10, description="Maximum number of products to return"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get top selling products by quantity sold.
    
    Args:
        limit: Maximum number of products to return
    
    Returns:
        List of dictionaries with product info and quantity sold
    """
    service = StatisticsService(db)
    return service.get_top_selling_products(limit=limit)


@router.get("/products/sold")
async def get_total_sold_by_product(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get total sold quantity by product.
    
    Returns:
        List of dictionaries with product info and total sold
    """
    service = StatisticsService(db)
    return service.get_total_sold_by_product()


@router.get("/products/total-sold")
async def get_total_sold_all_products(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get total sold quantity for all products.
    
    Returns:
        Total quantity sold
    """
    service = StatisticsService(db)
    total = service.get_total_sold_all_products()
    return {"total_sold": total}


@router.get("/todo")
async def get_todo_items(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get actionable todo items for the admin dashboard."""
    service = StatisticsService(db)
    return service.get_todo_items()
