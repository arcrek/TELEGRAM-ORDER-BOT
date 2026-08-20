"""
Run the dashboard API server.
"""
import os

import uvicorn

if __name__ == "__main__":
    # Use import string for reload to work properly
    # This allows uvicorn to reload on file changes
    reload = os.getenv("DASHBOARD_RELOAD", "true").lower() == "true"
    port = int(os.getenv("DASHBOARD_PORT", "8001"))
    
    if reload:
        # Use import string for reload functionality
        uvicorn.run(
            "src.dashboard.main:app",
            host="0.0.0.0",
            port=port,
            reload=True,
        )
    else:
        # Direct import for production (no reload)
        from src.dashboard.main import app
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            reload=False,
        )

