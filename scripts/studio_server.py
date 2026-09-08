"""Doctus Studio OS — Web Server Launcher (Hackathon & Non-Technical Demo).

Launches the production-grade, dark-red Tailwind CSS studio dashboard.
Designed for non-technical users, entertainment lawyers, and hackathon judges
to visually explore clearance, run pre-flight checks, inspect C2PA manifests,
approve countersignatures with one click, and execute the 8-beat demo arc.

Usage:
  uv run python scripts/studio_server.py [--port 8080] [--open]
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doctus.server.studio_server import create_studio_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Doctus Studio Web Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default 8080)")
    parser.add_argument("--db", type=Path, default=None, help="Path to SQLite graph database")
    parser.add_argument("--open", action="store_true", default=False, help="Open dashboard in browser")
    args = parser.parse_args()

    server, engine = create_studio_server(port=args.port, db_path=args.db)

    url = f"http://localhost:{args.port}"
    print("=" * 78)
    print("  DOCTUS STUDIO OS // CLEARANCE AS EXECUTABLE POLICY")
    print("  High-Performance Dark-Red SaaS Dashboard for Non-Technical Users")
    print("=" * 78)
    print(f"  Local Dashboard URL : {url}")
    print(f"  Fail-Closed Gate    : Active (< 5ms SLA)")
    print(f"  ClickHouse Mirror   : {type(engine.mirror._sim).__name__ if engine.mirror.is_mock else 'ClickHouse Cloud'}")
    print(f"  Trust Anchor PKI    : Doctus Root Authority (X.509)")
    print("=" * 78)
    print("  Press Ctrl+C to stop the studio server.\n")

    if args.open:
        def _open():
            time.sleep(0.5)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Doctus Studio server...")
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
