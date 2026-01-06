"""
Main FastAPI application for dashboard.
"""
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.dashboard.routers import auth, statistics, products, orders, suppliers, product_upload, pre_uploaded, variations, product_supplier_assignments, notifications

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="MTK Bot Order Dashboard API",
    description="Admin dashboard API for MTK Bot Order System",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["statistics"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["suppliers"])
app.include_router(product_upload.router, prefix="/api", tags=["product-upload"])
app.include_router(pre_uploaded.router, prefix="/api", tags=["pre-uploaded"])
app.include_router(variations.router, prefix="/api/variations", tags=["variations"])
app.include_router(product_supplier_assignments.router, prefix="/api/suppliers", tags=["product-supplier-assignments"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "MTK Bot Order Dashboard API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

