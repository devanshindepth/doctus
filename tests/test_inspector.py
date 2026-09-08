"""Tests for the visual inspector HTML generator (P6)."""
from __future__ import annotations

import datetime as dt

from doctus.engine.models import AssetRecord, Claim, ClaimKind, IngredientEdge
from doctus.engine.scope import Scope
from doctus.graph.store import RightsGraph
from doctus.inspector.generator import generate_inspector_html


def test_inspector_html_generation():
    graph = RightsGraph(":memory:")
    graph.add_asset(AssetRecord("ast_test_shot", "Hero Test"))
    graph.add_asset(AssetRecord("ast_test_audio", "Audio Test"))
    graph.add_edge(IngredientEdge("ast_test_shot", "ast_test_audio"))

    now = dt.datetime(2026, 8, 30, tzinfo=dt.timezone.utc)
    graph.add_claim(Claim(
        claim_id="clm_audio", kind=ClaimKind.MUSIC_CLEARANCE,
        asset_id="ast_test_audio", signer="test-signer", trusted=True,
        issued_at=now,
        scope=Scope(channels=frozenset({"festival"}), territories=frozenset({"US"})),
    ))

    graph.record_decision(
        ts=now.isoformat(), asset_id="ast_test_shot", verb="publish",
        channel="festival", territory="US", allowed=True, reason=None, detail=None,
        permissions_version=1,
    )

    html_out = generate_inspector_html(graph, title="Custom Test Inspector")

    assert "<!DOCTYPE html>" in html_out
    assert "Custom Test Inspector" in html_out
    assert "ast_test_shot" in html_out
    assert "ast_test_audio" in html_out
    assert "clm_audio" in html_out
    assert "ALLOWED" in html_out
    assert "E&amp;O Insurability Verification Certificate" in html_out
