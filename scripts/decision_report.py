"""Print the audit trail for one asset (or everything) as a deterministic report.

Usage:
    python scripts/decision_report.py <db-path> [asset_id]

The database is the rights-graph SQLite file; pass an asset id to scope the
report to its chain of decisions, or omit it for the full log. Output is
byte-stable for identical DB state (CONTEXT.md invariant 4), so it can be
diffed or attached to a policy claim as-is.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from doctus.engine.decisions import render_report  # noqa: E402
from doctus.graph.store import RightsGraph  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    db_path = Path(sys.argv[1])
    if not db_path.exists():
        print(f"error: no such database: {db_path}", file=sys.stderr)
        return 2
    graph = RightsGraph(db_path)
    asset_id = sys.argv[2] if len(sys.argv) > 2 else None
    decisions = graph.decisions_for(asset_id) if asset_id else graph.all_decisions()
    title = f"Doctus decision log — {asset_id}" if asset_id else "Doctus decision log"
    print(render_report(decisions, title=title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
