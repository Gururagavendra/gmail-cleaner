#!/usr/bin/env python3
"""
Gmail Bulk Unsubscribe Tool
---------------------------
A fast, Gmail-styled web app to find and unsubscribe from newsletters.

Usage:
    python main.py

Then open http://localhost:8766 in your browser.
"""

import os
import webbrowser
import threading

import server

# Use PORT from environment (for cloud hosting) or default to 8766
PORT = int(os.environ.get('PORT', 8766))


def main():
    print("=" * 60)
    print("📧 Gmail Bulk Unsubscribe Tool")
    print("=" * 60)
    
    # Check for credentials (file or environment variable)
    has_creds = os.path.exists('credentials.json') or os.environ.get('GOOGLE_CREDENTIALS')
    
    if not has_creds:
        print("\n⚠️  credentials.json not found!")
        print("\nSetup instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create project → Enable Gmail API")
        print("3. Create OAuth credentials (Desktop app)")
        print("4. Download JSON → rename to credentials.json")
        print("5. Put credentials.json in:", os.getcwd())
    else:
        print("\n✅ credentials.json found!")
    
    print(f"\n🌐 Opening browser at: http://localhost:{PORT}")
    print("   (Keep this terminal open)")
    print("\n   Press Ctrl+C to stop\n")
    
    # Only open browser if running locally (not in cloud)
    if not os.environ.get('PORT'):
        threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    
    # Start server
    server.start_server(PORT)


if __name__ == "__main__":
    main()
