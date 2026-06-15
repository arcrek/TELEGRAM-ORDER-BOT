"""
Main FastAPI application for dashboard.
"""

import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.dashboard.limiter import limiter

# Supplier functionality disabled
# from src.dashboard.routers import auth, statistics, products, orders, suppliers, product_upload, pre_uploaded, variations, product_supplier_assignments, notifications, payos_webhook, iotd
from src.dashboard.routers import (
    auth,
    statistics,
    products,
    orders,
    product_upload,
    pre_uploaded,
    variations,
    notifications,
    payos_webhook,
    iotd,
    bonus_tiers,
    discount_tiers,
    bot_ui_settings,
    balances,
    manuals,
)
from src.dashboard.routers import api_v1

# Load environment variables from .env file
load_dotenv()

# Configure logging so application loggers (src.*, including IPN processor and
# notification service) emit INFO-level messages alongside uvicorn's access log.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

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
def resolve_cors_origins(raw: str | None) -> list[str]:
    """Parse CORS_ORIGINS into an explicit allow-list.

    Wildcard is refused because the app sends credentials (cookies/Authorization),
    and `*` + credentials is both insecure and rejected by browsers.
    """
    if raw is None or not raw.strip():
        logging.getLogger(__name__).warning(
            "CORS_ORIGINS not set; defaulting to localhost dev origins. "
            "Set CORS_ORIGINS explicitly in production."
        )
        return ["http://localhost:5173", "http://localhost:3000"]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins:
        raise ValueError(
            "CORS_ORIGINS must list explicit origins; '*' is not allowed "
            "because the API uses credentialed requests."
        )
    return origins


allowed_origins = resolve_cors_origins(os.getenv("CORS_ORIGINS"))
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
app.include_router(discount_tiers.router, prefix="/api", tags=["discount-tiers"])
# Supplier functionality disabled
# app.include_router(product_supplier_assignments.router, prefix="/api/suppliers", tags=["product-supplier-assignments"])
app.include_router(
    notifications.router, prefix="/api/notifications", tags=["notifications"]
)
app.include_router(
    bot_ui_settings.router, prefix="/api/bot-ui-settings", tags=["bot-ui-settings"]
)
app.include_router(payos_webhook.router, prefix="/api/payos", tags=["payos"])
app.include_router(iotd.router, prefix="/api/iotd", tags=["iotd"])
app.include_router(balances.router, prefix="/api/balances", tags=["balances"])
app.include_router(manuals.router, prefix="/api/manuals", tags=["manuals"])
app.include_router(api_v1.router, prefix="/api/v1", tags=["public-api"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "MTK Bot Order Dashboard API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
