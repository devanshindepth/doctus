"""Clearance Gate: deterministic allow/deny around every side-effectful action.

Fail-closed (CONTEXT.md invariant 2). Every deny explains itself (invariant 3)
and writes a DecisionRecord (invariant 5).
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from doctus.engine.models import (CLAIM_VERBS, ClaimKind, DenyReason, GateVerdict,
                                  ProposedAction, Verb)
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
                                 detail=f"unknown asset '{action.asset_id}'", checked=checked)

        perms_row = self._effective(action.asset_id)
        checked += 1

        # 2. quarantine propagation
        quarantined = self._quarantined_ingredients(action.asset_id)
        if action.asset_id in quarantined:
            return self._verdict(action, False, DenyReason.QUARANTINED_INPUT,
                                 detail="asset itself failed provenance verification",
                                 checked=checked, permissions_version=version)

        # 3. untrusted-signer shadowing: any unverified claim in the closure taints
        #    the chain (fail-closed); verified-only chains are unaffected.
        untrusted = self._untrusted_in_closure(action.asset_id)
        if untrusted:
            return self._verdict(action, False, DenyReason.UNTRUSTED_SIGNER,
                                 detail=f"unverified claims present: {sorted(untrusted)}",
                                 checked=checked, permissions_version=version)

        # 4. verb granted at all?
        scopes = perms_row
        scope = scopes.get(action.verb)
        if scope is None or scope.is_empty():
            reason, hint, kind = self._explain_absent(action.asset_id, action.verb)
            return self._verdict(action, False, reason, detail=hint,
                                 missing_claim_kind=kind, negotiation_hint=hint,
                                 checked=checked, permissions_version=version)

        # 5. scope coverage — window lapse gets its own diagnosis: "renew", not
        #    "missing". A lapsed grant is more actionable than no grant.
        if scope.valid_until is not None and now >= scope.valid_until:
            return self._verdict(action, False, DenyReason.EXPIRED_WINDOW,
                                 detail=f"window expired at {scope.valid_until.isoformat()}",
                                 negotiation_hint="renew the license covering this use",
                                 checked=checked, permissions_version=version)
        ok, detail = scope.covers(channel=action.channel, territory=action.territory)
        if not ok:
            return self._verdict(action, False, DenyReason.SCOPE_EXCEEDED, detail=detail,
                                 negotiation_hint=f"extend scope: {detail}",
                                 checked=checked, permissions_version=version)

        return self._verdict(action, True, checked=checked, permissions_version=version)

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

    def _quarantined_ingredients(self, asset_id: str) -> set[str]:
        ids, _ = self.graph.ancestor_closure(asset_id)
        bad: set[str] = set()
        for aid in ids:
            claims = self.graph.claims_for([aid])
            if not claims:
                continue
            if all(not c.trusted for c in claims):
                bad.add(aid)
        return bad

    def _untrusted_in_closure(self, asset_id: str) -> list[str]:
        ids, _ = self.graph.ancestor_closure(asset_id)
        out: list[str] = []
        for aid in ids:
            for c in self.graph.claims_for([aid]):
                if not c.trusted:
                    out.append(f"{aid}:{c.claim_id}")
        return out

    def _explain_absent(self, asset_id: str, verb: Verb):
        """Name the missing claim type and the fix path (invariant 3).
        Distinguish 'an ingredient has no paperwork' (fix: clear it) from
        'paperwork exists everywhere but doesn't compose' (fix: new instrument)."""
        kinds = {k.value for k, vs in CLAIM_VERBS.items() if verb in vs}
        ids, acyclic = self.graph.ancestor_closure(asset_id)
        if not acyclic:
            return DenyReason.VERB_NOT_GRANTED, "ingredient cycle detected", None

        def covering(aid: str) -> bool:
            return any(c.trusted and c.kind.value in kinds
                       for c in self.graph.claims_for([aid]))

        bare_ingredients = [aid for aid in ids[1:] if not covering(aid)]
        if bare_ingredients:
            return DenyReason.INGREDIENT_UNCLEARED, (
                f"asset(s) {bare_ingredients} carry no verified claim granting "
                f"'{verb.value}'; need one of {sorted(kinds)}"), \
                ClaimKind(sorted(kinds)[0])
        n_sources = sum(1 for aid in ids if covering(aid))
        return DenyReason.VERB_NOT_GRANTED, (
            f"{n_sources} verified claim source(s) present but none grants "
            f"'{verb.value}' for this use; draft a new instrument"), \
            ClaimKind(sorted(kinds)[0])

    def _verdict(self, action: ProposedAction, allowed: bool, reason=None, *,
                 detail: str = "", missing_claim_kind=None, negotiation_hint=None,
                 checked: int = 0, permissions_version: int | None = None) -> GateVerdict:
        verdict = GateVerdict(
            allowed=allowed, asset_id=action.asset_id, verb=action.verb,
            reason=reason if not allowed else None,
            detail="" if allowed else detail,
            missing_claim_kind=missing_claim_kind if not allowed else None,
            negotiation_hint=negotiation_hint if not allowed else None,
            checked_claims=checked, permissions_version=permissions_version,
        )
        self.graph.record_decision(
            ts=self._now().isoformat(), asset_id=action.asset_id, verb=action.verb.value,
            allowed=allowed, reason=verdict.reason.value if verdict.reason else None,
            detail=verdict.detail or None, permissions_version=permissions_version,
        )
        return verdict


def _scopes_json(scopes) -> str:  # shared helper
    from doctus.engine.compiler import _scopes_to_json  # noqa: PLC0415

    return _scopes_to_json(scopes)
