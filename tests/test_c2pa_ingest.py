"""Round-trip suite: REAL signed media files -> ingest -> graph -> gate.

These tests exercise the P1 deliverable end-to-end against the prebaked
fixtures in fixtures/media (CONTEXT.md D9). They need c2pa-python and the
prebaked fixtures; both missing => skip with instructions rather than fail.
"""
from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pytest

pytest.importorskip("c2pa", reason="c2pa-python not installed")

REPO = Path(__file__).resolve().parent.parent
MEDIA = REPO / "fixtures" / "media"
ANCHOR = REPO / "fixtures" / "pki" / "demo_root.pem"


@pytest.fixture(scope="module", autouse=True)
def _require_prebaked():
    if not MEDIA.exists() or not ANCHOR.exists():
        pytest.skip("prebaked fixtures missing - run: python scripts/prebake_fixtures.py")


def _fixed_now(tz):
    return dt.datetime(2026, 9, 1, tzinfo=dt.UTC)


@pytest.fixture()
def ingested():
    """Fresh graph with all six fixtures ingested once."""
    from doctus.engine.compiler import PolicyCompiler
    from doctus.engine.gate import ClearanceGate
    from doctus.graph.ingest import ManifestIngester
    from doctus.graph.store import RightsGraph

    g = RightsGraph(":memory:")
    ingester = ManifestIngester(g, trust_anchors_pem=ANCHOR.read_text(encoding="utf-8"))
    reports = ingester.ingest_directory(MEDIA)
    gate = ClearanceGate(g, PolicyCompiler(g), now_fn=_fixed_now)
    return g, ingester, gate, {r.asset_id: r for r in reports}


# ------------------------------------------------------------------ ingest
def test_all_six_files_ingest(ingested):
    _, _, _, by_asset = ingested
    assert len(by_asset) == 6
    expected = {"ast_music_bed_v1", "ast_hero_shot_v1", "ast_composite_v1",
                "ast_talent_frame_v1", "ast_video_shot_v1", "ast_rogue_asset_v1"}
    assert set(by_asset) == expected


def test_trusted_files_ingest_clean(ingested):
    _, _, _, by_asset = ingested
    for aid in ("ast_music_bed_v1", "ast_hero_shot_v1", "ast_composite_v1",
                "ast_talent_frame_v1", "ast_video_shot_v1"):
        report = by_asset[aid]
        assert report.trusted and report.status == "INGESTED", report
        assert not report.failure_codes


def test_rogue_signature_is_quarantined(ingested):
    """Attack artifact: valid crypto, untrusted issuer -> quarantined (invariant 2)."""
    _, _, _, by_asset = ingested
    report = by_asset["ast_rogue_asset_v1"]
    assert not report.trusted and report.status == "QUARANTINED"
    assert "signingCredential.untrusted" in report.failure_codes
    # its wide-scope ODRL offer was stored (audit trail) but marked untrusted
    assert len(report.claim_ids) == 2


def test_edges_derive_from_native_c2pa_ingredients(ingested):
    _, _, _, by_asset = ingested
    edges = by_asset["ast_composite_v1"].edges
    assert ("ast_composite_v1", "ast_hero_shot_v1") in edges
    assert ("ast_composite_v1", "ast_music_bed_v1") in edges


def test_unsigned_file_reports_no_manifest(tmp_path):
    from PIL import Image
    from doctus.graph.ingest import ManifestIngester
    from doctus.graph.store import RightsGraph

    plain = tmp_path / "plain.jpg"
    Image.new("RGB", (8, 8), (0, 0, 0)).save(plain, format="JPEG")
    g = RightsGraph(":memory:")
    ingester = ManifestIngester(g, trust_anchors_pem=ANCHOR.read_text(encoding="utf-8"))
    report = ingester.ingest_file(plain)
    assert report.status == "NO_MANIFEST"
    assert report.asset_id is None and not report.claim_ids


def test_reingest_is_idempotent(ingested):
    g, ingester, _, _ = ingested
    before = sorted(r["claim_id"] for r in g._db.execute(
        "SELECT claim_id FROM claims").fetchall())
    assets_before = sorted(r["asset_id"] for r in g._db.execute(
        "SELECT asset_id FROM assets").fetchall())
    ingester.ingest_directory(MEDIA)
    after = sorted(r["claim_id"] for r in g._db.execute(
        "SELECT claim_id FROM claims").fetchall())
    assets_after = sorted(r["asset_id"] for r in g._db.execute(
        "SELECT asset_id FROM assets").fetchall())
    assert before == after
    assert assets_before == assets_after


# ------------------------------------------------------------------- gate
def test_signed_chain_publishes_within_scope(ingested):
    _, _, gate, _ = ingested
    v = gate.check(_act(channel="festival", territory="US"))
    assert v.allowed, v.detail


def test_same_file_blocked_outside_licensed_channel(ingested):
    _, _, gate, _ = ingested
    v = gate.check(_act(channel="trailer", territory="US"))
    assert not v.allowed and v.reason.value == "SCOPE_EXCEEDED"


def test_generation_only_original_has_no_usage_rights(ingested):
    _, _, gate, _ = ingested
    v = gate.check(_act(asset_id="ast_video_shot_v1", channel="social", territory="US"))
    assert not v.allowed and v.reason.value == "VERB_NOT_GRANTED"


def test_likeness_consent_covers_social_publish(ingested):
    _, _, gate, _ = ingested
    v = gate.check(_act(asset_id="ast_talent_frame_v1", channel="social", territory="US"))
    assert v.allowed, v.detail


def test_rogue_asset_itself_denied_quarantined_input(ingested):
    _, _, gate, _ = ingested
    v = gate.check(_act(asset_id="ast_rogue_asset_v1", channel="trailer", territory="EU"))
    assert not v.allowed and v.reason.value == "QUARANTINED_INPUT"


def test_untrusted_signer_shadows_downstream_children(ingested):
    """A derivative built ON the rogue asset is denied UNTRUSTED_SIGNER."""
    from doctus.engine.models import AssetRecord, ProposedAction, Verb
    from doctus.graph.store import IngredientEdge

    g, _, gate, _ = ingested
    g.add_asset(AssetRecord(asset_id="ast_child_of_rogue", label="composite using rogue"))
    g.add_edge(IngredientEdge(asset_id="ast_child_of_rogue", ingredient_id="ast_rogue_asset_v1"))
    v = gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="ast_child_of_rogue",
                                  channel="festival", territory="US"))
    assert not v.allowed and v.reason.value == "UNTRUSTED_SIGNER", v.reason
    assert "ast_rogue_asset_v1" in v.detail


# ---------------------------------------------------------------- helpers
def _act(asset_id: str = "ast_composite_v1", channel: str | None = None,
         territory: str | None = None):
    from doctus.engine.models import ProposedAction, Verb

    return ProposedAction(verb=Verb.PUBLISH, asset_id=asset_id,
                          channel=channel, territory=territory)
