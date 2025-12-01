"""
Gmail Cleaner - FastAPI Application
-----------------------------------
Main application factory and configuration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core import settings
from app.api import status_router, actions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    print(f"{settings.app_name} v{settings.app_version} starting...")
    yield
    # Shutdown
    print("Shutting down...")


def create_app() -> FastAPI:
    """Application factory - creates and configures the FastAPI app."""
    
    app = FastAPI(
        title=settings.app_name,
        description="Bulk unsubscribe and email management tool for Gmail",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Include API routers
    app.include_router(status_router)
    app.include_router(actions_router)
    
    # HTML routes
    @app.get("/", include_in_schema=False)
    async def root():
        """Serve the main HTML page."""
        return FileResponse("templates/index.html", media_type="text/html")
    
    @app.get("/index.html", include_in_schema=False)
    async def index():
        """Serve the main HTML page."""
        return FileResponse("templates/index.html", media_type="text/html")
    
    return app


# Create app instance
app = create_app()
