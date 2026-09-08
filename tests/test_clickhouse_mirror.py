"""Unit and integration tests for ClickHouse rights analytics mirror (P5)."""
from __future__ import annotations

import datetime as dt

from doctus.analytics.clickhouse import (
    ClickHouseConfig,
    ClickHouseMirror,
    ClickHouseSimulator,
)
from doctus.engine.models import AssetRecord, Claim, ClaimKind, IngredientEdge
from doctus.engine.scope import Scope
from doctus.graph.store import RightsGraph


def test_clickhouse_simulator_insert_and_select():
    sim = ClickHouseSimulator()
    sim.insert("doctus_assets", [{"asset_id": "ast_1", "label": "Shot 1"}])
    rows = sim.select("doctus_assets")
    assert len(rows) == 1
    assert rows[0]["asset_id"] == "ast_1"

    # Deduplication / replace on primary key
    sim.insert("doctus_assets", [{"asset_id": "ast_1", "label": "Updated Shot 1"}])
    rows2 = sim.select("doctus_assets")
    assert len(rows2) == 1
    assert rows2[0]["label"] == "Updated Shot 1"


def test_clickhouse_mirror_sync_from_sqlite():
    graph = RightsGraph(":memory:")
    graph.add_asset(AssetRecord("ast_shot_1", "Hero Take"))
    graph.add_asset(AssetRecord("ast_music_1", "Festival Track"))
    graph.add_edge(IngredientEdge("ast_shot_1", "ast_music_1"))

    now = dt.datetime(2026, 8, 30, tzinfo=dt.timezone.utc)
    graph.add_claim(Claim(
        claim_id="clm_1", kind=ClaimKind.LICENSE, asset_id="ast_music_1",
        signer="label-key", trusted=True, issued_at=now,
        valid_until=now + dt.timedelta(days=10),
        scope=Scope(channels=frozenset({"festival"}), territories=frozenset({"US"})),
    ))

    graph.record_decision(
        ts=now.isoformat(), asset_id="ast_shot_1", verb="publish",
        channel="trailer", territory="US", allowed=False,
        reason="SCOPE_EXCEEDED", detail="channel trailer not covered",
        permissions_version=1,
    )

    mirror = ClickHouseMirror(ClickHouseConfig(mock_mode=True))
    counts = mirror.sync_from_sqlite(graph)

    assert counts["assets"] == 2
    assert counts["edges"] == 1
    assert counts["claims"] == 1
    assert counts["decisions"] == 1

    # Verify query analytics
    latencies = mirror.get_gate_latency_percentiles()
    assert latencies["count"] == 1
    assert 0 < latencies["p50"] < 5.0

    denies = mirror.get_deny_reasons_histogram()
    assert denies.get("SCOPE_EXCEEDED") == 1

    alerts = mirror.get_expiring_window_alerts(within_days=15, now=now)
    assert len(alerts) == 1
    assert alerts[0]["claim_id"] == "clm_1"
    assert alerts[0]["status"] == "EXPIRING_SOON"

    summary = mirror.get_studio_executive_summary()
    assert summary["studio_assets"] == 2
    assert summary["verified_claims"] == 1
    assert summary["gate_decisions"] == 1
    assert summary["denies"] == 1
    assert summary["clearance_rate"] == 0.0


def test_clickhouse_stream_decision():
    mirror = ClickHouseMirror(ClickHouseConfig(mock_mode=True))
    mirror.stream_decision({
        "decision_id": 101,
        "ts": "2026-08-30T12:00:00Z",
        "asset_id": "ast_stream_test",
        "verb": "publish",
        "channel": "social",
        "territory": "US",
        "allowed": 1,
        "reason": None,
        "detail": None,
        "claims_evaluated_json": "{}",
        "action_json": "{}",
        "negotiation_hint": None,
        "permissions_version": 1,
    }, latency_ms=1.45)

    rows = mirror._get_table_rows("doctus_decisions")
    assert len(rows) == 1
    assert rows[0]["decision_id"] == 101
    assert rows[0]["latency_ms"] == 1.45

    pcts = mirror.get_gate_latency_percentiles()
    assert pcts["p50"] == 1.45
