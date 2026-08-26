"""P3 exit criterion (DESIGN.md §6): demo beats 1-5 end-to-end, locally.

Beat 1  agent generates a shot -> real signed C2PA manifest -> trusted ingest
Beat 2  likeness-consented talent asset publishes on its consented channel
Beat 3  agent composites shot + music bed -> native ingredient edges
Beat 4  compile reflects the chain: festival publish sails through
Beat 5  trailer publish DENIED with the named gap + an audit row

Runs against the committed prebaked media (D9); newly signed outputs land in
pytest's tmp dirs, never the repo tree. Needs c2pa-python + prebaked fixtures;
missing => skip with instructions rather than fail.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from doctus.agents import CountersignLedger, Negotiator
from doctus.engine.models import ClaimKind, Verb

pytest.importorskip("c2pa", reason="c2pa-python not installed")

REPO = Path(__file__).resolve().parent.parent
MEDIA = REPO / "fixtures" / "media"
ANCHOR = REPO / "fixtures" / "pki" / "demo_root.pem"
SIGNER_CERT = REPO / "fixtures" / "pki" / "demo_signer.pem"
SIGNER_KEY = REPO / "fixtures" / "pki" / "demo_signer.key"

NOW = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)


def _plain_jpeg(path: Path, caption: str) -> Path:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (320, 180), (10, 60, 120))
    ImageDraw.Draw(img).text((10, 80), caption, fill=(255, 255, 255))
    img.save(path, format="JPEG", quality=90)
    return path


@pytest.fixture(scope="module")
def studio(tmp_path_factory):
    """Graph with prebaked media ingested once + an agent holding demo PKI."""
    if not MEDIA.exists() or not ANCHOR.exists():
        pytest.skip("prebaked fixtures missing - run: python scripts/prebake_fixtures.py")
    scratch = tmp_path_factory.mktemp("studio")
    from doctus.agents import ProductionAgent
    from doctus.engine.compiler import PolicyCompiler
    from doctus.engine.gate import ClearanceGate
    from doctus.graph.ingest import ManifestIngester
    from doctus.graph.store import RightsGraph

    g = RightsGraph(":memory:")
    ingester = ManifestIngester(g, trust_anchors_pem=ANCHOR.read_text(encoding="utf-8"))
    ingester.ingest_directory(MEDIA)
    gate = ClearanceGate(g, PolicyCompiler(g), now_fn=lambda tz: NOW)
    agent = ProductionAgent(g, gate,
                            signer_cert_pem=SIGNER_CERT.read_bytes(),
                            signer_key_pem=SIGNER_KEY.read_bytes())
    return g, agent, ingester, scratch


# ------------------------------------------------------------------ beat 1
def test_beat_1_generated_asset_enters_graph_trusted(studio):
    g, agent, ingester, scratch = studio
    raw = _plain_jpeg(scratch / "_raw_shot.jpg", "VEO SHOT (runtime)")
    out = scratch / "ast_veo_shot_p3.jpg"
    result = agent.generate(src_media=str(raw), out_path=str(out),
                            asset_id="ast_veo_shot_p3",
                            label="agent-generated hero take")
    assert result.ok, result.detail

    report = ingester.ingest_file(out)
    assert report.status == "INGESTED" and report.trusted, report
    assert report.asset_id == "ast_veo_shot_p3"
    # provenance-of-origin claim came along; usage rights did not (Q5)
    kinds = {c.kind.value for c in g.claims_for([report.asset_id])}
    assert kinds == {"generation"}
    v = agent.check_permission(Verb.PUBLISH, "ast_unknown_asset",
                               channel="social")
    assert not v.allowed  # sanity: unknown asset still fails closed


# ------------------------------------------------------------------ beat 2
def test_beat_2_likeness_consent_publishes_on_consented_channel(studio):
    _, agent, _, _ = studio
    v = agent.publish(asset_id="ast_talent_frame_v1", channel="social", territory="US")
    assert v.ok, v.verdict.detail
    # same consent does NOT stretch to other channels
    v2 = agent.publish(asset_id="ast_talent_frame_v1", channel="trailer", territory="US")
    assert not v2.ok and v2.verdict.reason.value == "SCOPE_EXCEEDED"


# ------------------------------------------------------------------ beat 3
def test_beat_3_composite_wires_native_ingredient_edges(studio):
    g, agent, ingester, scratch = studio
    raw = _plain_jpeg(scratch / "_raw_composite.jpg", "COMPOSITE P3")
    out = scratch / "ast_composite_p3.jpg"
    result = agent.composite(
        src_media=str(raw), out_path=str(out), asset_id="ast_composite_p3",
        label="hero + bed composite (runtime)",
        ingredients=[("ast_hero_shot_v1", str(MEDIA / "ast_hero_shot_v1.jpg")),
                     ("ast_music_bed_v1", str(MEDIA / "ast_music_bed_v1.jpg"))])
    assert result.ok, result.detail

    report = ingester.ingest_file(out)
    assert report.status == "INGESTED" and report.trusted, report
    assert ("ast_composite_p3", "ast_hero_shot_v1") in report.edges
    assert ("ast_composite_p3", "ast_music_bed_v1") in report.edges
    closure, acyclic = g.ancestor_closure("ast_composite_p3")
    assert acyclic and set(closure) == {"ast_composite_p3", "ast_hero_shot_v1",
                                        "ast_music_bed_v1"}


# ------------------------------------------------------------------ beat 4
def test_beat_4_compiled_permissions_cover_festival_publish(studio):
    _, agent, _, _ = studio
    v = agent.publish(asset_id="ast_composite_p3", channel="festival", territory="US")
    assert v.ok, v.verdict.detail
    assert v.verdict.decision_id is not None  # allow carries its audit row ref


# ------------------------------------------------------------------ beat 5
def test_beat_5_trailer_publish_denied_with_named_gap(studio):
    g, agent, _, _ = studio
    v = agent.publish(asset_id="ast_composite_p3", channel="trailer", territory="US")
    assert not v.ok
    verdict = v.verdict
    assert verdict.reason.value == "SCOPE_EXCEEDED"
    assert "'trailer' outside ['festival']" in verdict.detail
    assert "extend scope" in verdict.negotiation_hint

    # the deny is a first-class audit artifact (invariant 5)
    rows = [d for d in g.decisions_for("ast_composite_p3") if not d["allowed"]]
    assert rows and rows[-1]["reason"] == "SCOPE_EXCEEDED"
    assert rows[-1]["claims_evaluated_json"]["count"] > 0


# ------------------------------------------------------------- fail-closed
def test_generate_without_signer_material_is_refused(studio):
    g, agent, _, _ = studio
    from doctus.agents import ProductionAgent

    naked = ProductionAgent(g, None)
    result = naked.generate(src_media="x", out_path="y", asset_id="ast_z")
    assert not result.ok and "no signer material" in result.detail


# --------------------------------------------- negotiation semantics (D5)
def _negotiate_and_approve(g, agent, kind: ClaimKind) -> None:
    """Beat 5 deny -> draft extension on the bed -> human countersign."""
    v = agent.publish(asset_id="ast_composite_p3", channel="trailer", territory="US")
    assert not v.ok and v.verdict.reason.value == "SCOPE_EXCEEDED"
    draft = Negotiator().draft_extension(
        v.verdict, asset_id="ast_music_bed_v1", channels=["trailer"],
        territories=["US"],
        until=dt.datetime(2027, 6, 1, tzinfo=dt.UTC), kind=kind)
    ledger = CountersignLedger(g)
    ledger.propose(draft, proposed_by="negotiator-v1")
    ledger.approve(draft, approver="human-studio-lead")


@pytest.fixture()
def fresh_studio(tmp_path):
    """Isolated graph per test: these cases MUTATE the composite's ancestry,
    so they cannot share the module-scoped studio fixture."""
    if not MEDIA.exists() or not ANCHOR.exists():
        pytest.skip("prebaked fixtures missing - run: python scripts/prebake_fixtures.py")
    from doctus.agents import ProductionAgent
    from doctus.engine.compiler import PolicyCompiler
    from doctus.engine.gate import ClearanceGate
    from doctus.graph.ingest import ManifestIngester
    from doctus.graph.store import RightsGraph

    g = RightsGraph(":memory:")
    ingester = ManifestIngester(g, trust_anchors_pem=ANCHOR.read_text(encoding="utf-8"))
    ingester.ingest_directory(MEDIA)
    gate = ClearanceGate(g, PolicyCompiler(g), now_fn=lambda tz: NOW)
    agent = ProductionAgent(g, gate,
                            signer_cert_pem=SIGNER_CERT.read_bytes(),
                            signer_key_pem=SIGNER_KEY.read_bytes())
    raw = _plain_jpeg(tmp_path / "_raw_composite.jpg", "COMPOSITE P3")
    res = agent.composite(src_media=str(raw), out_path=str(tmp_path / "c.jpg"),
                          asset_id="ast_composite_p3",
                          ingredients=[("ast_hero_shot_v1", str(MEDIA / "ast_hero_shot_v1.jpg")),
                                       ("ast_music_bed_v1", str(MEDIA / "ast_music_bed_v1.jpg"))])
    assert res.ok
    ingester.ingest_file(tmp_path / "c.jpg")
    return g, agent


def test_same_class_extension_reopens_the_channel(fresh_studio):
    """The bed's prebaked instrument is an ODRL Offer -> LICENSE. Extending the
    SAME class unions within that source (festival OR trailer) -> publish passes.
    This is beats 6-8 of the demo arc against real signed media."""
    g, agent = fresh_studio
    _negotiate_and_approve(g, agent, ClaimKind.LICENSE)
    v = agent.publish(asset_id="ast_composite_p3", channel="trailer", territory="US")
    assert v.ok, v.verdict.detail
    # festival still covered too - a union never narrows existing grants
    v2 = agent.publish(asset_id="ast_composite_p3", channel="festival", territory="US")
    assert v2.ok


def test_wrong_class_extension_cannot_widen(fresh_studio):
    """A music_clearance extension on a license-covered bed is a DIFFERENT
    source: cross-source intersection collapses channels to empty and the
    verb dies entirely (invariant 1 - denies never widen). Pinned so nobody
    'fixes' this into a silent widening later."""
    g, agent = fresh_studio
    _negotiate_and_approve(g, agent, ClaimKind.MUSIC_CLEARANCE)
    v = agent.publish(asset_id="ast_composite_p3", channel="trailer", territory="US")
    assert not v.ok and v.verdict.reason.value == "VERB_NOT_GRANTED"

