#!/usr/bin/env python3
"""
Doctus Dashboard launcher.

Usage:
    uv run python scripts/serve_dashboard.py          # default port 8000
    uv run python scripts/serve_dashboard.py --port 8080
    uv run python scripts/serve_dashboard.py --reload  # hot-reload for dev

Opens the browser automatically.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Doctus Dashboard")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload (dev mode)")
    parser.add_argument("--no-browser", action="store_true", help="Skip opening browser")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent

    cmd = [
        sys.executable, "-m", "uvicorn",
        "dashboard.api:app",
        "--host", args.host,
        "--port", str(args.port),
    ]
    if args.reload:
        cmd.append("--reload")

    url = f"http://{args.host}:{args.port}"
    print(f"\n  ⚖️  Doctus AI Rights Clearance Studio")
    print(f"  ──────────────────────────────────────")
    print(f"  Dashboard → {url}")
    print(f"  API docs  → {url}/docs")
    print(f"  Press Ctrl+C to stop\n")

    if not args.no_browser:
        import threading, time
        def _open():
            time.sleep(1.4)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    try:
        subprocess.run(cmd, cwd=str(repo), check=True)
    except KeyboardInterrupt:
        print("\n  Dashboard stopped.")


if __name__ == "__main__":
    main()
