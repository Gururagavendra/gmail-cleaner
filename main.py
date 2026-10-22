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
from app.api.auth import get_effective_token, token_was_generated


def main():
    print("=" * 60)
    print(f"{settings.app_name}")
    print("=" * 60)

    # Check for credentials (file or environment variable)
    has_creds = os.path.exists(settings.credentials_file) or os.environ.get(
        "GOOGLE_CREDENTIALS"
    )

    if not has_creds:
        print(f"\nERROR: {settings.credentials_file} not found!")
        print("\nSetup instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create project -> Enable Gmail API")
        print("3. Create OAuth credentials (Desktop app)")
        print("4. Download JSON -> rename to credentials.json")
        print("5. Put credentials.json in:", os.getcwd())
        print("\nExiting. Please add credentials.json and try again.")
        return

    print(f"\n{settings.credentials_file} found!")

    port = int(os.environ.get("PORT", settings.port))
    host = settings.host

    # Report the API authentication posture so the operator is never surprised.
    token = get_effective_token()
    if token:
        if token_was_generated():
            print("\nAPI authentication: ENABLED (auto-generated token)")
            print(f"   API token: {token}")
            print("   The web UI authenticates automatically in the browser.")
            print("   Use this token for direct API/CLI calls:")
            print('   Authorization: Bearer <token>   (or cookie api_token=<token>)')
            print("   Set API_TOKEN in the environment to pin a stable token.")
        else:
            print("\nAPI authentication: ENABLED (API_TOKEN from environment)")
    else:
        print(f"\nAPI authentication: disabled (loopback-only bind on {host})")

    print(f"\nOpening browser at: http://localhost:{port}")
    print("   (Keep this terminal open)")
    print("\n   Press Ctrl+C to stop\n")

    # Only open browser if running locally (not in cloud)
    if not os.environ.get("PORT"):
        threading.Timer(
            1.0, lambda: webbrowser.open(f"http://localhost:{port}")
        ).start()

    # Start FastAPI with Uvicorn. Host defaults to loopback (see Settings.host);
    # set HOST=0.0.0.0 to listen on all interfaces (required inside Docker).
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
