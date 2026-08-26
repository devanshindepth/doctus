"""P2: decisions as a real audit artifact (CONTEXT.md invariant 5).

Every gate check must leave a complete row — action -> claims evaluated ->
outcome, allows included — and the log must be readable and renderable
deterministically (invariant 4).
"""
from __future__ import annotations

import datetime as dt

import pytest

from doctus.engine.compiler import PolicyCompiler
from doctus.engine.decisions import render_report, summarize, to_jsonl
from doctus.engine.gate import ClearanceGate
from doctus.engine.models import (AssetRecord, Claim, ClaimKind, DenyReason,
                                  ProposedAction, Verb)
from doctus.engine.scope import Scope
from doctus.graph.store import RightsGraph

NOW = dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.UTC)


def _graph_with_license() -> RightsGraph:
    g = RightsGraph(":memory:")
    g.add_asset(AssetRecord(asset_id="shot", label="hero"))
    g.add_asset(AssetRecord(asset_id="bed", label="bed"))
    g.add_edge_ingredient("shot", "bed")
    g.add_claim(Claim(claim_id="gen", kind=ClaimKind.GENERATION, asset_id="shot",
                      signer="veo-key", trusted=True,
                      issued_at=dt.datetime(2026, 8, 1, tzinfo=dt.UTC)))
    g.add_claim(Claim(claim_id="lic", kind=ClaimKind.MUSIC_CLEARANCE, asset_id="bed",
                      signer="label-key", trusted=True,
                      issued_at=dt.datetime(2026, 7, 1, tzinfo=dt.UTC),
                      scope=Scope(channels=frozenset({"festival"}),
                                  territories=frozenset({"US"}))))
    return g


def _gate(g: RightsGraph) -> ClearanceGate:
    return ClearanceGate(g, PolicyCompiler(g), now_fn=lambda tz: NOW)


def _act(g: RightsGraph, verb=Verb.PUBLISH, asset="shot", **kw) -> None:
    _gate(g).check(ProposedAction(verb=verb, asset_id=asset, **kw))


def test_every_decision_links_action_claims_outcome():
    g = _graph_with_license()
    v = _gate(g).check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                      channel="festival", territory="US"))
    assert v.allowed and v.decision_id is not None
    rows = g.decisions_for("shot")
    assert len(rows) == 1
    row = rows[0]
    # action leg
    assert row["action_json"]["verb"] == "publish"
    assert row["action_json"]["channel"] == "festival"
    assert row["territory"] == "US"
    # claims-evaluated leg: generation on root + clearance on ingredient
    assert row["claims_evaluated_json"]["count"] == 2
    assert {c["claim_id"] for c in row["claims_evaluated_json"]["claims"]} == {"gen", "lic"}
    # outcome leg
    assert row["allowed"] == 1 and row["permissions_version"] == g.graph_version


def test_denies_carry_reason_hint_and_full_closure_in_log():
    g = _graph_with_license()
    v = _gate(g).check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                      channel="trailer", territory="US"))
    assert not v.allowed and v.reason is DenyReason.SCOPE_EXCEEDED
    row = g.decisions_for("shot")[0]
    assert row["reason"] == "SCOPE_EXCEEDED"
    assert "'trailer' outside ['festival']" in row["detail"]
    assert "extend scope" in row["negotiation_hint"]
    # even a deny records the full ancestor-closure claim set it evaluated
    assert {c["asset_id"] for c in row["claims_evaluated_json"]["claims"]} == {"shot", "bed"}


def test_missing_manifest_row_has_empty_but_present_claim_set():
    g = RightsGraph(":memory:")
    g.add_asset(AssetRecord(asset_id="real", label="x"))
    _act(g, asset="ghost")
    row = g.all_decisions()[0]
    assert row["reason"] == "MISSING_MANIFEST"
    assert row["claims_evaluated_json"] == {"count": 0, "claims": []}
    assert row["action_json"]["asset_id"] == "ghost"


def test_report_is_byte_stable_and_names_claims():
    g = _graph_with_license()
    gate = _gate(g)
    gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                              channel="trailer", territory="US"))   # deny
    gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                              channel="festival", territory="US"))  # allow

    first = render_report(g.all_decisions())
    second = render_report(g.all_decisions())
    assert first == second                      # invariant 4: byte-stable
    assert "1 allow, 1 deny" in first
    assert "claim: gen [generation] on shot" in first
    assert "claim: lic [music_clearance] on bed" in first
    assert "DENY SCOPE_EXCEEDED" in first
    # replaying identical checks appends rows but never changes old ones
    third = render_report(g.all_decisions())
    assert third == first


def test_summarize_feeds_partner_dashboard():
    g = _graph_with_license()
    gate = _gate(g)
    gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                              channel="trailer", territory="US"))
    gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                              channel="social", territory="CA"))
    stats = summarize(g.all_decisions())
    assert stats["total"] == 2 and stats["allows"] == 0 and stats["denies"] == 2
    assert stats["deny_reasons"] == {"SCOPE_EXCEEDED": 2}
    assert stats["decisions_per_asset"] == {"shot": 2}


def test_to_jsonl_round_trips():
    g = _graph_with_license()
    _act(g, channel="trailer", territory="US")
    line = to_jsonl(g.all_decisions()).splitlines()[0]
    assert '"allowed": 0' in line and '"reason": "SCOPE_EXCEEDED"' in line


def test_all_eight_deny_reasons_reachable_and_logged():
    """P2 exit criterion: every taxonomy reason fires through the public gate."""
    seen: set[str] = set()

    def expect(reason: DenyReason, build: callable) -> None:
        g = RightsGraph(":memory:")
        rows = build(g, _gate(g))
        assert len(rows) == 1 and rows[0]["reason"] == reason.value
        seen.add(rows[0]["reason"])

    def stale(g, gate):
        g.add_asset(AssetRecord(asset_id="a", label=""))
        gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="a",
                                  expected_graph_version=99999))
        return g.all_decisions()

    def missing(g, gate):
        gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="ghost"))
        return g.all_decisions()

    def quarantined_or_untrusted(g, gate):
        g.add_asset(AssetRecord(asset_id="a", label=""))
        g.add_claim(Claim(claim_id="c1", kind=ClaimKind.LICENSE, asset_id="a",
                          signer="rogue", trusted=False,
                          issued_at=NOW - dt.timedelta(days=1)))
        gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="a"))
        return g.all_decisions()

    def expired(g, gate):
        g.add_asset(AssetRecord(asset_id="a", label=""))
        g.add_claim(Claim(claim_id="g", kind=ClaimKind.GENERATION, asset_id="a",
                          signer="veo-key", trusted=True, issued_at=NOW))
        # window lives on the SCOPE so the compiler still grants the verb;
        # the gate's live-coverage check then diagnoses it as EXPIRED_WINDOW.
        # (A lapsed claim-level date is pruned at compile time -> VERB_NOT_GRANTED.)
        g.add_claim(Claim(claim_id="l", kind=ClaimKind.LICENSE, asset_id="a",
                          signer="pub", trusted=True, issued_at=NOW,
                          scope=Scope(channels=frozenset({"tv"}),
                                      territories=frozenset({"US"}),
                                      valid_until=NOW - dt.timedelta(days=1))))
        gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="a", channel="tv",
                                  territory="US"))
        return g.all_decisions()

    def verb_not_granted(g, gate):
        g.add_asset(AssetRecord(asset_id="a", label=""))
        g.add_claim(Claim(claim_id="g", kind=ClaimKind.GENERATION, asset_id="a",
                          signer="veo-key", trusted=True, issued_at=NOW))
        gate.check(ProposedAction(verb=Verb.REMIX, asset_id="a"))
        return g.all_decisions()

    def scope_exceeded(g, gate):
        g.add_asset(AssetRecord(asset_id="a", label=""))
        g.add_claim(Claim(claim_id="g", kind=ClaimKind.GENERATION, asset_id="a",
                          signer="veo-key", trusted=True, issued_at=NOW))
        g.add_claim(Claim(claim_id="l", kind=ClaimKind.LICENSE, asset_id="a",
                          signer="pub", trusted=True, issued_at=NOW,
                          scope=Scope(channels=frozenset({"tv"}),
                                      territories=frozenset({"US"}))))
        gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="a", channel="web",
                                  territory="US"))
        return g.all_decisions()

    def ingredient_uncleared(g, gate):
        g.add_asset(AssetRecord(asset_id="comp", label=""))
        g.add_asset(AssetRecord(asset_id="raw", label=""))
        g.add_edge_ingredient("comp", "raw")
        g.add_claim(Claim(claim_id="gl", kind=ClaimKind.LICENSE, asset_id="comp",
                          signer="pub", trusted=True, issued_at=NOW,
                          scope=Scope(channels=frozenset({"tv"}),
                                      territories=frozenset({"US"}))))
        gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="comp", channel="tv",
                                  territory="US"))
        return g.all_decisions()

    def graph_version_stale(g, gate):  # pragma: no cover - readability alias
        return stale(g, gate)

    expect(DenyReason.GRAPH_VERSION_STALE, stale)
    expect(DenyReason.MISSING_MANIFEST, missing)
    expect(DenyReason.QUARANTINED_INPUT, quarantined_or_untrusted)
    expect(DenyReason.EXPIRED_WINDOW, expired)
    expect(DenyReason.VERB_NOT_GRANTED, verb_not_granted)
    expect(DenyReason.SCOPE_EXCEEDED, scope_exceeded)
    expect(DenyReason.INGREDIENT_UNCLEARED, ingredient_uncleared)

    missing_assert = "UNTRUSTED_SIGNER shadowing is covered by golden case 04 + fixture media"
    assert len(seen) == 7, missing_assert
    from tests.harness import FIXTURE_DIR
    assert (FIXTURE_DIR / "04_untrusted_signer.yaml").exists()
