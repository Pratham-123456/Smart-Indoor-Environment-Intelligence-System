"""SIEIS Unified One-Click Launcher.

Initializes database, starts Flask server, and automatically opens
the web dashboard in the default browser.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import threading
import time
import webbrowser

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from config import Config


def open_browser():
    """Waits 1.2s for server initialization then opens the web dashboard."""
    time.sleep(1.2)
    url = f"http://localhost:{Config.PORT}/"
    print(f"\n[SIEIS Launcher] Opening dashboard in browser: {url}")
    webbrowser.open(url)


def main():
    print("=" * 65)
    print("  SIEIS — Smart Indoor Environmental Intelligence System")
    print("  Unified Edge-to-Cloud Intelligence Platform")
    print("=" * 65)
    print(f"Server Port: {Config.PORT}")
    print(f"Database:    {Config.DATABASE_PATH}")
    print(f"Device Target: {Config.EXPECTED_DEVICE_ID}")

    # Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Create and run Flask application
    app = create_app(Config)
    print("\n[SIEIS Server] Running... Press Ctrl+C to stop.\n")
    app.run(host=Config.HOST, port=Config.PORT, debug=False)


if __name__ == "__main__":
    main()
