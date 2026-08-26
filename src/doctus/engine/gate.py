"""Clearance Gate: deterministic allow/deny around every side-effectful action.

Fail-closed (CONTEXT.md invariant 2). Every deny explains itself (invariant 3),
and EVERY decision — allows too — writes a DecisionRecord linking
action -> claims evaluated -> outcome (invariant 5). The trail IS the product
for insurers/E&O.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any

from doctus.engine.compiler import _has_generation_only
from doctus.engine.models import (CLAIM_VERBS, ClaimKind, Claim, DenyReason,
                                  GateVerdict, ProposedAction, Verb,
                                  _set_decision_id)
from doctus.engine.permissions_store import ensure_table


class ClearanceGate:
    def __init__(self, graph, compiler, now_fn=dt.datetime.now) -> None:
        self.graph = graph
        self.compiler = compiler
        self._now_fn = now_fn

    def _now(self) -> dt.datetime:
        return self._now_fn(dt.UTC)

    def check(self, action: ProposedAction) -> GateVerdict:
        now = self._now()
        checked = 0

        # 0. stale-plan protection
        version = self.graph.graph_version
        if action.expected_graph_version is not None and action.expected_graph_version != version:
            return self._verdict(action, False, DenyReason.GRAPH_VERSION_STALE,
                                 detail=f"planned against {action.expected_graph_version}, "
                                        f"graph now at {version}", checked=checked)

        # 1. unknown / manifest-less asset
        asset = self.graph.get_asset(action.asset_id)
        if asset is None:
            return self._verdict(action, False, DenyReason.MISSING_MANIFEST,
                                 detail=f"unknown asset '{action.asset_id}'",
                                 checked=checked)

        perms_row = self._effective(action.asset_id)
        checked += 1

        # 2+3. ONE pass over the ancestor closure feeds both quarantine
        #      propagation and untrusted-signer shadowing (fail-closed).
        closure, acyclic = self.graph.ancestor_closure(action.asset_id)
        claims = self.graph.claims_for(closure)
        quarantined, untrusted = _closure_taint(closure, claims)
        if action.asset_id in quarantined:
            return self._verdict(action, False, DenyReason.QUARANTINED_INPUT,
                                 detail="asset itself failed provenance verification",
                                 checked=checked, permissions_version=version,
                                 claims=claims)
        if untrusted:
            return self._verdict(action, False, DenyReason.UNTRUSTED_SIGNER,
                                 detail=f"unverified claims present: {sorted(untrusted)}",
                                 checked=checked, permissions_version=version,
                                 claims=claims)

        # 4. verb granted at all?
        scopes = perms_row
        scope = scopes.get(action.verb)
        if scope is None or scope.is_empty():
            reason, hint, kind = self._explain_absent(action.asset_id, action.verb,
                                                      closure, acyclic, claims)
            return self._verdict(action, False, reason, detail=hint,
                                 missing_claim_kind=kind, negotiation_hint=hint,
                                 checked=checked, permissions_version=version,
                                 claims=claims)

        # 5. scope coverage — window lapse gets its own diagnosis: "renew", not
        #    "missing". A lapsed grant is more actionable than no grant.
        if scope.valid_until is not None and now >= scope.valid_until:
            return self._verdict(action, False, DenyReason.EXPIRED_WINDOW,
                                 detail=f"window expired at {scope.valid_until.isoformat()}",
                                 negotiation_hint="renew the license covering this use",
                                 checked=checked, permissions_version=version,
                                 claims=claims)
        ok, detail = scope.covers(channel=action.channel, territory=action.territory)
        if not ok:
            return self._verdict(action, False, DenyReason.SCOPE_EXCEEDED, detail=detail,
                                 negotiation_hint=f"extend scope: {detail}",
                                 checked=checked, permissions_version=version,
                                 claims=claims)

        return self._verdict(action, True, checked=checked,
                             permissions_version=version, claims=claims)

    # ------------------------------------------------------------ internals
    def _effective(self, asset_id: str) -> dict[Verb, Any]:
        """Compile fresh, materialize, return live scopes. Correctness first;
        the upsert keeps the cache warm for analytics/mirroring."""
        ensure_table(self.graph._db)
        from doctus.engine.permissions_store import upsert  # noqa: PLC0415
        current = self.compiler.compile_asset(asset_id, now=self._now())
        upsert(self.graph._db, current.asset_id, current.graph_version,
               current.compiled_at.isoformat(), current.policy_version,
               _scopes_json(current.scopes), current.constraints_hash)
        return dict(current.scopes)

    def _explain_absent(self, asset_id: str, verb: Verb, closure: list[str],
                        acyclic: bool, claims: list[Claim]):
        """Name the missing claim type and the fix path (invariant 3).
        Distinguish 'an ingredient has no paperwork' (fix: clear it) from
        'paperwork exists everywhere but doesn't compose' (fix: new instrument)."""
        kinds = {k.value for k, vs in CLAIM_VERBS.items() if verb in vs}
        if not acyclic:
            return DenyReason.VERB_NOT_GRANTED, "ingredient cycle detected", None

        by_asset: dict[str, list[Claim]] = {}
        for c in claims:
            by_asset.setdefault(c.asset_id, []).append(c)

        def covering(aid: str) -> bool:
            # Mirror the compiler's notion of "covered": a fully-owned
            # original carrying only a verified generation claim counts
            # (its wildcard is narrowed by other sources), otherwise any
            # trusted claim whose kind can grant this verb.
            return (any(c.trusted and c.kind.value in kinds
                        for c in by_asset.get(aid, ()))
                    or _has_generation_only(aid, claims))

        bare_ingredients = [aid for aid in closure[1:] if not covering(aid)]
        if bare_ingredients:
            return DenyReason.INGREDIENT_UNCLEARED, (
                f"asset(s) {bare_ingredients} carry no verified claim granting "
                f"'{verb.value}'; need one of {sorted(kinds)}"), \
                ClaimKind(sorted(kinds)[0])
        n_sources = sum(1 for aid in closure if covering(aid))
        return DenyReason.VERB_NOT_GRANTED, (
            f"{n_sources} verified claim source(s) present but none grants "
            f"'{verb.value}' for this use; draft a new instrument"), \
            ClaimKind(sorted(kinds)[0])

    def _verdict(self, action: ProposedAction, allowed: bool, reason=None, *,
                 detail: str = "", missing_claim_kind=None, negotiation_hint=None,
                 checked: int = 0, permissions_version: int | None = None,
                 claims: list[Claim] | None = None) -> GateVerdict:
        verdict = GateVerdict(
            allowed=allowed, asset_id=action.asset_id, verb=action.verb,
            reason=reason if not allowed else None,
            detail="" if allowed else detail,
            missing_claim_kind=missing_claim_kind if not allowed else None,
            negotiation_hint=negotiation_hint if not allowed else None,
            checked_claims=checked, permissions_version=permissions_version,
        )
        claims_evaluated = {
            "count": len(claims or []),
            "claims": [
                {"claim_id": c.claim_id, "kind": c.kind.value,
                 "asset_id": c.asset_id, "signer": c.signer,
                 "trusted": bool(c.trusted)}
                for c in (claims or [])
            ],
        }
        _set_decision_id(verdict, self.graph.record_decision(
            ts=self._now().isoformat(), asset_id=action.asset_id,
            verb=action.verb.value, allowed=allowed,
            reason=verdict.reason.value if verdict.reason else None,
            detail=verdict.detail or None, permissions_version=permissions_version,
            channel=action.channel, territory=action.territory,
            claims_evaluated_json=json.dumps(claims_evaluated, sort_keys=True),
            action_json=json.dumps({
                "verb": action.verb.value, "asset_id": action.asset_id,
                "channel": action.channel, "territory": action.territory,
                "recipient": action.recipient,
                "expected_graph_version": action.expected_graph_version,
            }, sort_keys=True),
            negotiation_hint=negotiation_hint,
        ))
        return verdict


def _closure_taint(closure: list[str], claims: list[Claim]) -> tuple[set[str], list[str]]:
    """Single-pass classification of a closure's claims.

    Returns (quarantined_assets, untrusted_refs) where an asset is quarantined
    iff it has claims and ALL of them are unverified (store-level ingest
    failure); untrusted_refs lists every individual unverified claim."""
    by_asset: dict[str, list[Claim]] = {aid: [] for aid in closure}
    for c in claims:
        by_asset[c.asset_id].append(c)
    quarantined = {aid for aid, cs in by_asset.items() if cs and all(not c.trusted for c in cs)}
    untrusted = [f"{aid}:{c.claim_id}"
                 for aid in closure for c in by_asset[aid] if not c.trusted]
    return quarantined, untrusted


def _scopes_json(scopes) -> str:  # shared helper
    from doctus.engine.compiler import _scopes_to_json  # noqa: PLC0415

    return _scopes_to_json(scopes)
