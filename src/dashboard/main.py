"""
Main FastAPI application for dashboard.
"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
# Supplier functionality disabled
# from src.dashboard.routers import auth, statistics, products, orders, suppliers, product_upload, pre_uploaded, variations, product_supplier_assignments, notifications, payos_webhook, iotd
from src.dashboard.routers import auth, statistics, products, orders, product_upload, pre_uploaded, variations, notifications, payos_webhook, iotd, bonus_tiers

# Load environment variables from .env file
load_dotenv()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MTK Bot Order Dashboard API",
    description="Admin dashboard API for MTK Bot Order System",
    version="1.0.0",
)

# Disable redirect_slashes on the router to prevent 307 redirects
app.router.redirect_slashes = False

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - configure with environment variable
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["statistics"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
# Supplier functionality disabled
# app.include_router(suppliers.router, prefix="/api/suppliers", tags=["suppliers"])
app.include_router(product_upload.router, prefix="/api", tags=["product-upload"])
app.include_router(pre_uploaded.router, prefix="/api", tags=["pre-uploaded"])
app.include_router(variations.router, prefix="/api/variations", tags=["variations"])
app.include_router(bonus_tiers.router, prefix="/api", tags=["bonus-tiers"])
# Supplier functionality disabled
# app.include_router(product_supplier_assignments.router, prefix="/api/suppliers", tags=["product-supplier-assignments"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(payos_webhook.router, prefix="/api/payos", tags=["payos"])
app.include_router(iotd.router, prefix="/api/iotd", tags=["iotd"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "MTK Bot Order Dashboard API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

