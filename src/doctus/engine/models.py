"""Typed domain models: verbs, claims, assets, actions, verdicts, deny taxonomy.

The claim->verb vocabulary below pins open question Q5 (CONTEXT.md): the ODRL
action subset Doctus honors in v1. Generation claims authorize nothing by
themselves — they only establish provenance of origin.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from doctus.engine.scope import Scope


class Verb(str, Enum):
    PUBLISH = "publish"
    REMIX = "remix"
    TRAIN_ON = "train_on"
    LICENSE_OUT = "license_out"


class ClaimKind(str, Enum):
    GENERATION = "generation"
    LICENSE = "license"
    LIKENESS_CONSENT = "likeness_consent"
    MUSIC_CLEARANCE = "music_clearance"
    TRAINING_CONSENT = "training_consent"


#: Q5 vocabulary pin — which claim kinds grant which verbs (v1 subset).
CLAIM_VERBS: dict[ClaimKind, tuple[Verb, ...]] = {
    ClaimKind.LICENSE: (Verb.PUBLISH, Verb.REMIX, Verb.LICENSE_OUT),
    ClaimKind.LIKENESS_CONSENT: (Verb.PUBLISH,),
    ClaimKind.MUSIC_CLEARANCE: (Verb.PUBLISH,),
    ClaimKind.TRAINING_CONSENT: (Verb.TRAIN_ON,),
}


@dataclass(frozen=True)
class Claim:
    """A signed assertion riding in an asset's C2PA manifest store."""

    claim_id: str
    kind: ClaimKind
    asset_id: str
    signer: str
    trusted: bool
    issued_at: dt.datetime
    valid_from: dt.datetime | None = None
    valid_until: dt.datetime | None = None
    scope: Scope | None = None          # None for generation claims
    odrl: dict[str, Any] = field(default_factory=dict)  # raw ODRL 2.2 JSON-LD payload


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    label: str


@dataclass(frozen=True)
class IngredientEdge:
    """Topology only: 'consumer' derived from 'ingredient'. Claims never ride edges in v1."""

    asset_id: str
    ingredient_id: str


@dataclass(frozen=True)
class ProposedAction:
    """A side-effectful action the production agent wants to take."""

    verb: Verb
    asset_id: str
    channel: str | None = None
    territory: str | None = None
    recipient: str | None = None
    expected_graph_version: int | None = None  # replay/stale protection


class DenyReason(str, Enum):
    MISSING_MANIFEST = "MISSING_MANIFEST"
    UNTRUSTED_SIGNER = "UNTRUSTED_SIGNER"
    EXPIRED_WINDOW = "EXPIRED_WINDOW"
    VERB_NOT_GRANTED = "VERB_NOT_GRANTED"
    SCOPE_EXCEEDED = "SCOPE_EXCEEDED"
    INGREDIENT_UNCLEARED = "INGREDIENT_UNCLEARED"
    QUARANTINED_INPUT = "QUARANTINED_INPUT"
    GRAPH_VERSION_STALE = "GRAPH_VERSION_STALE"


@dataclass(frozen=True)
class PermissionSet:
    """Compiled output per asset. Absent verb == not granted (fail-closed)."""

    asset_id: str
    graph_version: int
    compiled_at: dt.datetime
    policy_version: str
    scopes: dict[Verb, Scope]
    constraints_hash: str

    def grants(self, verb: Verb) -> bool:
        return verb in self.scopes and not self.scopes[verb].is_empty()


@dataclass(frozen=True)
class GateVerdict:
    allowed: bool
    asset_id: str
    verb: Verb
    reason: DenyReason | None = None
    detail: str = ""
    missing_claim_kind: ClaimKind | None = None
    negotiation_hint: str | None = None
    checked_claims: int = 0
    permissions_version: int | None = None
    decision_id: int | None = None  # back-reference into the decisions log


def _set_decision_id(v: "GateVerdict", decision_id: int) -> None:
    object.__setattr__(v, "decision_id", decision_id)
