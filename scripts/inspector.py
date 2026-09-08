"""Doctus Visual Inspector CLI (P6, DESIGN.md §3.1.1/§6).

Renders a self-contained interactive HTML audit report from a Doctus SQLite graph DB.
Can export to a standalone .html file or serve locally via a lightweight HTTP server.

Usage:
  uv run python scripts/inspector.py [--db doctus.db] [--output inspector.html] [--serve]
"""
from __future__ import annotations

import argparse
import http.server
import socketserver
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doctus.inspector.generator import generate_inspector_html  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Doctus Visual Inspector HTML")
    parser.add_argument("--db", type=Path, default=None, help="Path to Doctus SQLite DB")
    parser.add_argument("--output", type=Path, default=REPO / "scratch" / "inspector.html",
                        help="Path to output HTML file")
    parser.add_argument("--serve", action="store_true", help="Start a local web server to view the report")
    parser.add_argument("--port", type=int, default=8080, help="Port for the local web server")
    args = parser.parse_args()

    db_path = args.db
    if not db_path or not db_path.exists():
        # Fall back to running an in-memory sample arc or inspecting demo DB
        print(f"DB not specified or not found ({db_path}); generating from mock demo state...")
        from doctus.engine.models import AssetRecord, Claim, ClaimKind, IngredientEdge
        from doctus.engine.scope import Scope
        from doctus.graph.store import RightsGraph
        import datetime as dt

        graph = RightsGraph(":memory:")
        graph.add_asset(AssetRecord("ast_veo_shot", "Veo Hero Take"))
        graph.add_asset(AssetRecord("ast_music_bed_v1", "Festival Music Bed"))
        graph.add_asset(AssetRecord("ast_composite_v1", "Composite Trailer"))
        graph.add_edge(IngredientEdge("ast_composite_v1", "ast_veo_shot"))
        graph.add_edge(IngredientEdge("ast_composite_v1", "ast_music_bed_v1"))

        now = dt.datetime.now(dt.timezone.utc)
        graph.add_claim(Claim(
            claim_id="clm_veo_gen", kind=ClaimKind.GENERATION,
            asset_id="ast_veo_shot", signer="google-veo-key", trusted=True,
            issued_at=now,
        ))
        graph.add_claim(Claim(
            claim_id="clm_music_lic", kind=ClaimKind.LICENSE,
            asset_id="ast_music_bed_v1", signer="label-records-key", trusted=True,
            issued_at=now,
            scope=Scope(channels=frozenset({"festival"}), territories=frozenset({"US"})),
        ))
        graph.record_decision(
            ts=now.isoformat(), asset_id="ast_composite_v1", verb="publish",
            channel="festival", territory="US", allowed=True, reason=None, detail=None,
            permissions_version=1,
        )
        graph.record_decision(
            ts=now.isoformat(), asset_id="ast_composite_v1", verb="publish",
            channel="trailer", territory="US", allowed=False, reason="SCOPE_EXCEEDED",
            detail="channel 'trailer' not covered by music license",
            negotiation_hint="extend scope of ast_music_bed_v1 to include channel trailer",
            permissions_version=1,
        )
        html_content = generate_inspector_html(graph)
    else:
        html_content = generate_inspector_html(db_path)

    out_path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"[OK] Visual Inspector written to: {out_path} ({len(html_content):,} bytes)")

    if args.serve:
        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))

        print(f"Serving Inspector at http://localhost:{args.port} (Ctrl+C to stop)...")
        with socketserver.TCPServer(("", args.port), Handler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
