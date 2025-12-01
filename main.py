#!/usr/bin/env python3
"""
Gmail Bulk Unsubscribe Tool
---------------------------
A fast, Gmail-styled web app to find and unsubscribe from newsletters.

Usage:
    uv run python main.py

Then open http://localhost:8766 in your browser.
"""

import os
import webbrowser
import threading

import uvicorn

from app.core import settings
from app.main import app


def main():
    print("=" * 60)
    print(f"{settings.app_name}")
    print("=" * 60)
    
    # Check for credentials (file or environment variable)
    has_creds = os.path.exists(settings.credentials_file) or os.environ.get('GOOGLE_CREDENTIALS')
    
    if not has_creds:
        print(f"\n{settings.credentials_file} not found!")
        print("\nSetup instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create project -> Enable Gmail API")
        print("3. Create OAuth credentials (Desktop app)")
        print("4. Download JSON -> rename to credentials.json")
        print("5. Put credentials.json in:", os.getcwd())
    else:
        print(f"\n{settings.credentials_file} found!")
    
    port = int(os.environ.get('PORT', settings.port))
    
    print(f"\nOpening browser at: http://localhost:{port}")
    print("   (Keep this terminal open)")
    print("\n   Press Ctrl+C to stop\n")
    
    # Only open browser if running locally (not in cloud)
    if not os.environ.get('PORT'):
        threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    
    # Start FastAPI with Uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
