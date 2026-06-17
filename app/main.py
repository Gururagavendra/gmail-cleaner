"""
Gmail Cleaner - FastAPI Application
-----------------------------------
Main application factory and configuration.
"""

import hashlib
import os
import subprocess
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core import settings
from app.api import status_router, actions_router

templates = Jinja2Templates(directory="templates")


def get_asset_hash() -> str | None:
    """Hash served frontend assets so Docker builds without git still bust caches."""
    asset_paths = []
    for directory in ("static", "templates"):
        if not os.path.isdir(directory):
            continue
        for root, _dirs, files in os.walk(directory):
            for file_name in files:
                if file_name.endswith((".css", ".html", ".js")):
                    asset_paths.append(os.path.join(root, file_name))

    if not asset_paths:
        return None

    hasher = hashlib.sha256()
    for file_path in sorted(asset_paths):
        hasher.update(file_path.encode())
        try:
            with open(file_path, "rb") as f:
                hasher.update(f.read())
        except OSError:
            pass

    return hasher.hexdigest()[:8]


def get_cache_bust_value() -> str:
    """
    Get cache-busting value using a robust strategy:
    1. Try git commit hash (most specific)
    2. If uncommitted changes exist in static files, append a hash of those changes
    3. Fall back to app version from settings
    4. Fall back to timestamp if both unavailable
    """
    base_value = None

    # Try git commit hash first
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        commit_hash = result.stdout.strip()
        if commit_hash:
            base_value = commit_hash
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        pass

    # Check for uncommitted changes in static files
    if base_value:
        try:
            # Check for uncommitted changes in static directory
            diff_result = subprocess.run(
                ["git", "diff", "--name-only", "static/"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )

            # Also check for untracked files in static directory
            untracked_result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "static/"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )

            changed_files = diff_result.stdout.strip().splitlines()
            untracked_files = untracked_result.stdout.strip().splitlines()
            all_changed = [f for f in changed_files + untracked_files if f]

            if all_changed:
                # Compute hash of changed file names and their content
                hasher = hashlib.sha256()
                for file_path in sorted(all_changed):
                    # Validate file path is in static directory (security check)
                    if not file_path.startswith("static/"):
                        continue
                    hasher.update(file_path.encode())
                    try:
                        with open(file_path, "rb") as f:
                            hasher.update(f.read())
                    except OSError:
                        # Skip files that can't be read
                        pass
                change_hash = hasher.hexdigest()[:8]
                return f"{base_value}-{change_hash}"
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            pass

    # If we have a base value (commit hash), use it
    if base_value:
        return base_value

    # Docker images may not contain .git, so use frontend asset content.
    asset_hash = get_asset_hash()
    if asset_hash:
        return asset_hash

    # Fall back to app version
    if settings.app_version:
        return settings.app_version

    # Final fallback to timestamp
    return str(int(time.time()))


# Cache-busting value generated at app startup
STARTUP_CACHE_BUST = get_cache_bust_value()


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
        return templates.TemplateResponse(
            request,
            "index.html",
            {"cache_bust": STARTUP_CACHE_BUST, "version": settings.app_version},
        )

    return app


# Create app instance
app = create_app()
