"""
Gmail Cleaner - FastAPI Application
-----------------------------------
Main application factory and configuration.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core import settings
from app.api import status_router, actions_router

# Cache-busting: timestamp generated at app startup
STARTUP_TIME = str(int(time.time()))

templates = Jinja2Templates(directory="templates")


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
    async def root(request: Request):
        """Serve the main HTML page."""
        return templates.TemplateResponse(request, "index.html", {
        "cache_bust": STARTUP_TIME,
            "version": settings.app_version
        })

    return app


# Create app instance
app = create_app()
