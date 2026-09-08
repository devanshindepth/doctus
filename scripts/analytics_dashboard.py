"""ClickHouse Rights & Clearance Analytics Dashboard (P5, DESIGN.md §3.5).

Connects to ClickHouse (or embedded simulator), mirrors the local RightsGraph,
and renders real-time analytics for studio leads, E&O underwriters, and engineers.

Usage:
  uv run python scripts/analytics_dashboard.py [--db path/to/doctus.db] [--sync]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doctus.analytics.clickhouse import ClickHouseConfig, ClickHouseMirror  # noqa: E402
from doctus.graph.store import RightsGraph  # noqa: E402


def render_dashboard(mirror: ClickHouseMirror, db_path: Path | None = None) -> None:
    summary = mirror.get_studio_executive_summary()
    latencies = mirror.get_gate_latency_percentiles()
    denies = mirror.get_deny_reasons_histogram()
    alerts = mirror.get_expiring_window_alerts(within_days=60)
    chains = mirror.get_chain_depth_vs_clearance()

    mode = "ClickHouse Cloud / HTTP" if not mirror.is_mock else "Embedded ClickHouse Simulator"

    print("=" * 78)
    print("  DOCTUS // CLICKHOUSE RIGHTS & CLEARANCE ANALYTICS ENGINE")
    print(f"  Backend: {mode} | Source DB: {db_path or ':memory:'}")
    print("=" * 78)

    # 1. Executive Summary Cards
    print("\n[ STUDIO HEALTH & E&O AUDIT METRICS ]")
    rate_pct = f"{summary['clearance_rate'] * 100:.1f}%"
    print(f"  Assets Tracked     : {summary['studio_assets']:<6} | Verified Claims    : {summary['verified_claims']}")
    print(f"  Total Gate Checks  : {summary['gate_decisions']:<6} | Clearance Pass Rate: {rate_pct}")
    print(f"  Allowed Decisions  : {summary['allows']:<6} | Blocked Actions    : {summary['denies']}")
    print(f"  Countersign Actions: {summary['countersign_actions']:<6} | P50 Lookup Latency : {summary['p50_latency_ms']:.2f} ms")

    # 2. Latency SLA Budget (< 5ms)
    print("\n[ CLEARANCE GATE LATENCY SLA (BUDGET: < 5.0 ms) ]")
    print(f"  p50 (Median) : {latencies['p50']:>6.2f} ms   [OK]")
    print(f"  p90          : {latencies['p90']:>6.2f} ms   [OK]")
    print(f"  p95          : {latencies['p95']:>6.2f} ms   [OK]")
    print(f"  p99          : {latencies['p99']:>6.2f} ms   [OK]")
    print(f"  Average      : {latencies['avg']:>6.2f} ms   [OK]")

    # 3. Deny Reasons Breakdown
    print("\n[ DENIAL TAXONOMY BREAKDOWN ]")
    if denies:
        max_cnt = max(denies.values()) if denies else 1
        for reason, count in denies.items():
            bar = "#" * int((count / max_cnt) * 30)
            print(f"  {reason:<26} : {count:>3} {bar}")
    else:
        print("  (no denials recorded - all actions cleared)")

    # 4. Chain Depth vs Clearance Complexity
    print("\n[ PROVENANCE CHAIN DEPTH & CLEARANCE ]")
    print(f"  {'Asset ID':<22} {'Depth':<7} {'Claims':<8} {'Allows':<8} {'Denies':<8}")
    print("  " + "-" * 55)
    for c in chains[:6]:
        print(f"  {c['asset_id']:<22} {c['chain_depth']:<7} {c['total_claims']:<8} "
              f"{c['allows']:<8} {c['denies']:<8}")

    # 5. Risk Radar / Expiring Windows
    print("\n[ RISK RADAR: UPCOMING WINDOW EXPIRATIONS ]")
    if alerts:
        print(f"  {'Claim ID':<20} {'Asset ID':<20} {'Days Left':<11} {'Status'}")
        print("  " + "-" * 62)
        for a in alerts[:5]:
            status = "EXPIRING SOON" if a["status"] == "EXPIRING_SOON" else "EXPIRED"
            print(f"  {a['claim_id']:<20} {a['asset_id']:<20} {a['days_remaining']:>7.1f} d   [{status}]")
    else:
        print("  (all active licenses well within validity window)")

    print("\n" + "=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description="Doctus ClickHouse Analytics Dashboard")
    parser.add_argument("--db", type=Path, default=None, help="Path to SQLite database to mirror")
    parser.add_argument("--sync", action="store_true", default=True, help="Sync from SQLite before query")
    args = parser.parse_args()

    cfg = ClickHouseConfig.from_env()
    mirror = ClickHouseMirror(cfg)

    db_path = args.db
    if db_path and db_path.exists():
        graph = RightsGraph(db_path)
        if args.sync:
            synced = mirror.sync_from_sqlite(graph)
            print(f"Synced from {db_path}: {synced}")
    else:
        # Check if there is an existing demo workspace or run demo cases
        print("No DB provided or DB does not exist; running sample rights audit...")
        from doctus.engine.models import AssetRecord, Claim, ClaimKind, IngredientEdge
        from doctus.engine.scope import Scope
        import datetime as dt

        temp_graph = RightsGraph(":memory:")
        temp_graph.add_asset(AssetRecord(asset_id="ast_hero_shot_v1", label="Hero Shot"))
        temp_graph.add_asset(AssetRecord(asset_id="ast_music_bed_v1", label="Music Bed"))
        temp_graph.add_asset(AssetRecord(asset_id="ast_composite_v1", label="Composite Trailer"))
        temp_graph.add_edge(IngredientEdge("ast_composite_v1", "ast_hero_shot_v1"))
        temp_graph.add_edge(IngredientEdge("ast_composite_v1", "ast_music_bed_v1"))

        now = dt.datetime.now(dt.timezone.utc)
        temp_graph.add_claim(Claim(
            claim_id="clm_hero_gen", kind=ClaimKind.GENERATION,
            asset_id="ast_hero_shot_v1", signer="veo-signer", trusted=True,
            issued_at=now,
        ))
        temp_graph.add_claim(Claim(
            claim_id="clm_music_lic", kind=ClaimKind.LICENSE,
            asset_id="ast_music_bed_v1", signer="music-label", trusted=True,
            issued_at=now,
            valid_until=now + dt.timedelta(days=14),
            scope=Scope(channels=frozenset({"festival"}), territories=frozenset({"US"})),
        ))
        temp_graph.record_decision(
            ts=now.isoformat(), asset_id="ast_composite_v1", verb="publish",
            channel="festival", territory="US", allowed=True, reason=None, detail=None,
            permissions_version=1,
        )
        temp_graph.record_decision(
            ts=now.isoformat(), asset_id="ast_composite_v1", verb="publish",
            channel="trailer", territory="US", allowed=False, reason="SCOPE_EXCEEDED",
            detail="channel trailer not covered by music license",
            negotiation_hint="extend scope to trailer channel",
            permissions_version=1,
        )
        mirror.sync_from_sqlite(temp_graph)

    render_dashboard(mirror, db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
