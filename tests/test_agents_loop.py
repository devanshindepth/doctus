"""P3: negotiator + countersign ledger — the human-approval seam (invariant 6).

The negotiator drafts; only an explicit approval turns a draft into a
graph-valid claim. Every transition must be auditable and every misuse
(double-sign, approve-unproposed) loud.
"""
from __future__ import annotations

import datetime as dt

import pytest

from doctus.agents.countersign import (AlreadyApprovedError, CountersignLedger,
                                       DraftNotProposedError)
from doctus.agents.negotiator import DraftInstrument, Negotiator
from doctus.engine.compiler import PolicyCompiler
from doctus.engine.gate import ClearanceGate
from doctus.engine.models import (AssetRecord, Claim, ClaimKind, DenyReason,
                                  ProposedAction, Verb)
from doctus.engine.scope import Scope
from doctus.graph.store import RightsGraph

NOW = dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.UTC)
UNTIL_EXT = dt.datetime(2027, 6, 1, tzinfo=dt.UTC)


def _graph_with_festival_only_bed() -> RightsGraph:
    """shot <- bed with a festival-only music clearance (demo arc shape)."""
    g = RightsGraph(":memory:")
    g.add_asset(AssetRecord(asset_id="shot", label="hero"))
    g.add_asset(AssetRecord(asset_id="bed", label="bed"))
    g.add_edge_ingredient("shot", "bed")
    g.add_claim(Claim(claim_id="gen", kind=ClaimKind.GENERATION, asset_id="shot",
                      signer="veo-key", trusted=True, issued_at=NOW))
    g.add_claim(Claim(claim_id="lic", kind=ClaimKind.MUSIC_CLEARANCE, asset_id="bed",
                      signer="label-key", trusted=True, issued_at=NOW,
                      scope=Scope(channels=frozenset({"festival"}),
                                  territories=frozenset({"US"}),
                                  valid_until=dt.datetime(2027, 1, 1, tzinfo=dt.UTC))))
    return g


def _gate(g: RightsGraph) -> ClearanceGate:
    return ClearanceGate(g, PolicyCompiler(g), now_fn=lambda tz: NOW)


# ------------------------------------------------------------- negotiator
def test_scope_deny_yields_draftable_instrument():
    g = _graph_with_festival_only_bed()
    verdict = _gate(g).check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                            channel="trailer", territory="US"))
    assert not verdict.allowed and verdict.reason is DenyReason.SCOPE_EXCEEDED
    draft = Negotiator().draft_extension(
        verdict, asset_id="bed", channels=["trailer"], territories=["US"],
        until=UNTIL_EXT, kind=ClaimKind.MUSIC_CLEARANCE)
    assert draft.claim_kind is ClaimKind.MUSIC_CLEARANCE
    assert draft.draft_id.startswith("urn:doctus:draft:")
    # the instrument names the exact gap it cures
    constraint_channels = draft.odrl["permission"][0]["constraint"][0]["rightOperand"]
    assert constraint_channels == ["trailer"]
    assert "SCOPE_EXCEEDED" in draft.summary


def test_verb_absent_deny_uses_missing_claim_kind():
    """A deny carrying missing_claim_kind needs no explicit kind from the caller."""
    g = _graph_with_festival_only_bed()
    verdict = _gate(g).check(ProposedAction(verb=Verb.REMIX, asset_id="shot"))
    assert verdict.reason is DenyReason.INGREDIENT_UNCLEARED
    assert verdict.missing_claim_kind is not None
    draft = Negotiator().draft_extension(
        verdict, asset_id="bed", channels=["social"], territories=["US"],
        until=UNTIL_EXT)
    assert draft.claim_kind is verdict.missing_claim_kind


def test_negotiator_refuses_empty_deal_terms():
    g = _graph_with_festival_only_bed()
    verdict = _gate(g).check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                            channel="trailer", territory="US"))
    with pytest.raises(ValueError, match="empty channel"):
        Negotiator().draft_extension(verdict, asset_id="bed", channels=[],
                                     territories=["US"], kind=ClaimKind.LICENSE)


def test_negotiator_needs_a_kind_when_verdict_names_none():
    g = _graph_with_festival_only_bed()
    verdict = _gate(g).check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                            channel="trailer", territory="US"))
    with pytest.raises(ValueError, match="names no claim kind"):
        Negotiator().draft_extension(verdict, asset_id="bed",
                                     channels=["trailer"], territories=["US"])


def test_negotiator_refuses_allowed_actions_and_generation():
    g = _graph_with_festival_only_bed()
    verdict = _gate(g).check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                            channel="festival", territory="US"))
    assert verdict.allowed
    with pytest.raises(ValueError, match="nothing to negotiate"):
        Negotiator().draft_extension(verdict, asset_id="bed",
                                     channels=["festival"], territories=["US"])
    deny = _gate(g).check(ProposedAction(verb=Verb.REMIX, asset_id="shot"))
    with pytest.raises(ValueError, match="cannot negotiate"):
        Negotiator().draft_extension(deny, asset_id="shot", channels=["social"],
                                     territories=["US"],
                                     kind=ClaimKind.GENERATION)


# -------------------------------------------------------- countersign ledger
def _approved_claim_flow(g: RightsGraph):
    gate = _gate(g)
    verdict = gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                        channel="trailer", territory="US"))
    draft = Negotiator().draft_extension(
        verdict, asset_id="bed", channels=["trailer"], territories=["US"],
        until=UNTIL_EXT, kind=ClaimKind.MUSIC_CLEARANCE)
    ledger = CountersignLedger(g)
    ledger.propose(draft, proposed_by="negotiator-v1")
    return gate, draft, ledger


def test_approval_turns_draft_into_graph_valid_claim():
    g = _graph_with_festival_only_bed()
    gate, draft, ledger = _approved_claim_flow(g)
    claim_id = ledger.approve(draft, approver="human-studio-lead")

    claims = [c for c in g.claims_for(["bed"]) if c.claim_id == claim_id]
    assert len(claims) == 1, "approved claim must exist on the target asset"
    claim = claims[0]
    assert claim.trusted, "a countersigned claim is a verified claim"
    assert claim.signer == "human-studio-lead"
    assert claim.valid_until is not None

    # the SAME action now sails through (deny -> fix -> allow loop)
    after = gate.check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                      channel="trailer", territory="US"))
    assert after.allowed, after.detail
    # graph_version moved when the claim landed
    assert g.graph_version > 0


def test_approving_unproposed_draft_is_rejected():
    g = _graph_with_festival_only_bed()
    _, _, ledger = _approved_claim_flow(g)  # populates one full flow
    verdict = _gate(g).check(ProposedAction(verb=Verb.PUBLISH, asset_id="shot",
                                            channel="social", territory="US"))
    stray = DraftInstrument(
        draft_id="urn:doctus:draft:never-seen", asset_id="bed",
        claim_kind=ClaimKind.MUSIC_CLEARANCE, odrl={},
        summary="", drafted_from_hint="")
    with pytest.raises(DraftNotProposedError):
        ledger.approve(stray, approver="human")


def test_double_approval_is_loud():
    g = _graph_with_festival_only_bed()
    _, draft, ledger = _approved_claim_flow(g)
    ledger.approve(draft, approver="human-studio-lead")
    with pytest.raises(AlreadyApprovedError):
        ledger.approve(draft, approver="human-studio-lead")


def test_ledger_history_is_the_human_leg_of_the_audit_trail():
    g = _graph_with_festival_only_bed()
    _, draft, ledger = _approved_claim_flow(g)
    claim_id = ledger.approve(draft, approver="human-studio-lead")
    history = ledger.history()
    actions = [h["action"] for h in history]
    assert actions == ["PROPOSE", "APPROVE"]
    assert history[1]["claim_id"] == claim_id
    assert history[1]["actor"] == "human-studio-lead"
    assert ledger.pending() == []
