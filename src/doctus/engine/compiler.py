"""Policy Compiler: signed claims -> effective permission sets.

Deterministic. Same graph + same policy version => byte-identical output
(CONTEXT.md invariant 4). Compilation can only narrow (invariant 1):
- untrusted claims contribute nothing;
- generation claims authorize nothing by themselves;
- grants FROM THE SAME SOURCE (asset, claim kind) are alternatives => union;
- unions are then intersected ACROSS sources => every cross-source constraint holds;
- any source in the ancestry lacking a live claim for a verb kills the verb.

Known v1 simplification (documented in CONTEXT.md §5 note): deny records do not
yet prune union branches (deny-dominance is v2). Union only merges positive
grants from one signer class; a deny cannot widen anything.
"""
from __future__ import annotations

import datetime as dt

POLICY_VERSION = "1.1.0"

from collections import defaultdict

from doctus.engine.models import CLAIM_VERBS, ClaimKind, Claim, PermissionSet, Verb
from doctus.engine.scope import EMPTY_SCOPE, Scope, wildcard_scope


class PolicyCompiler:
    def __init__(self, graph) -> None:
        self.graph = graph

    # ------------------------------------------------------------------ API
    def compile_asset(self, asset_id: str, now: dt.datetime | None = None) -> PermissionSet:
        now = now or dt.datetime.now(dt.UTC)
        closure, acyclic = self.graph.ancestor_closure(asset_id)
        if not self.graph.get_asset(asset_id):
            raise KeyError(f"unknown asset: {asset_id}")
        if not acyclic:
            return self._materialize(asset_id, now, {})

        claims = [c for c in self.graph.claims_for(closure)]
        origin_established = False
        # same-source grants are alternatives: group by (source asset, claim kind)
        groups: dict[tuple[str, ClaimKind], list[Scope]] = defaultdict(list)

        for claim in claims:
            if not claim.trusted or not _live(claim, now):
                continue
            if claim.kind is ClaimKind.GENERATION:
                if claim.asset_id == asset_id:
                    origin_established = True   # provenance of origin only
                continue
            assert claim.scope is not None      # kind-guaranteed by models
            groups[(claim.asset_id, claim.kind)].append(claim.scope)

        result: dict[Verb, Scope] = {}
        for verb in Verb:
            relevant = {k: v for k, v in groups.items() if verb in CLAIM_VERBS[k[1]]}
            if not relevant:
                continue                        # no verified claims => verb absent
            # union within each source, then intersect across sources
            acc = wildcard_scope()
            for key in sorted(relevant, key=lambda kv: (kv[0], kv[1].value)):
                merged = _reduce_union(relevant[key])
                acc = acc.intersect(merged)
                if acc.is_empty():
                    break
            # every ancestor must contribute at least one live covering claim,
            # else fail-closed (a silent ancestor is an uncleared ancestor).
            covered = {aid for aid, kind in relevant}
            missing = [a for a in closure
                       if a != asset_id
                       and a not in covered
                       and not _has_generation_only(a, claims)]
            if asset_id not in covered and not origin_established:
                missing.append(asset_id)
            if missing or acc.is_empty():
                continue                        # verb stays absent
            result[verb] = acc

        return self._materialize(asset_id, now, result)

    def recompile_all(self, now: dt.datetime | None = None) -> list[str]:
        """Recompile + materialize every asset. Returns asset ids done."""
        done: list[str] = []
        rows = self.graph._db.execute("SELECT asset_id FROM assets").fetchall()
        from doctus.engine.permissions_store import upsert  # noqa: PLC0415
        for row in rows:
            perms = self.compile_asset(row["asset_id"], now=now)
            upsert(self.graph._db, perms.asset_id, perms.graph_version,
                   perms.compiled_at.isoformat(), perms.policy_version,
                   _scopes_to_json(perms.scopes), perms.constraints_hash)
            done.append(row["asset_id"])
        return done

    # ------------------------------------------------------------- internals
    def _materialize(self, asset_id: str, now: dt.datetime,
                     result: dict[Verb, Scope]) -> PermissionSet:
        payload = _scopes_to_json(result)
        digest = _hash(payload + POLICY_VERSION)
        return PermissionSet(
            asset_id=asset_id,
            graph_version=self.graph.graph_version,
            compiled_at=now,
            policy_version=POLICY_VERSION,
            scopes=result,
            constraints_hash=digest,
        )


# ------------------------------------------------------------------ helpers
def _live(claim: Claim, now: dt.datetime) -> bool:
    if claim.valid_from is not None and now < claim.valid_from:
        return False
    if claim.valid_until is not None and now >= claim.valid_until:
        return False
    return True


def _reduce_union(scopes: list[Scope]) -> Scope:
    acc = scopes[0]
    for s in scopes[1:]:
        acc = acc.union(s)
    return acc


def _has_generation_only(asset_id: str, claims: list[Claim]) -> bool:
    """Fully-owned originals may carry only a generation claim — treated as covered."""
    mine = [c for c in claims if c.asset_id == asset_id]
    return bool(mine) and all(c.kind is ClaimKind.GENERATION for c in mine)


def _scopes_to_json(scopes: dict[Verb, Scope]) -> str:
    import json  # noqa: PLC0415

    def one(s: Scope) -> dict:
        return {
            "channels": sorted(s.channels), "territories": sorted(s.territories),
            "valid_until": s.valid_until.isoformat() if s.valid_until else None,
            "exclusions": sorted(s.exclusions), "unlimited": s.unlimited,
        }
    return json.dumps({v.value: one(s) for v, s in sorted(scopes.items())}, sort_keys=True)


def _hash(text: str) -> str:
    import hashlib  # noqa: PLC0415

    return hashlib.sha256(text.encode()).hexdigest()[:16]
