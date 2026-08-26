"""Negotiator: deny explanations -> draft instruments. Never self-signs.

DESIGN.md §3.4 / CONTEXT.md invariant 6: the negotiation agent may *draft*
licenses and consents; only a human approval turns one into a graph-valid
signed claim (the countersign ledger). The v1 negotiator is deterministic —
it maps the gate's verdict onto a minimal ODRL instrument naming the exact
gap — which keeps the loop golden-testable. The P6 LLM negotiator will consume
the same verdict payload and emit the same DraftInstrument shape.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from doctus.engine.models import ClaimKind, GateVerdict

#: claim kind -> ODRL @type used by the ingest mapper (graph/ingest.py).
#: generation is absent on purpose: generation claims authorize nothing,
#: so no negotiable instrument can have that kind.
_ODRL_TYPE = {
    ClaimKind.LICENSE: "Offer",
    ClaimKind.LIKENESS_CONSENT: "Agreement",
    ClaimKind.MUSIC_CLEARANCE: "Offer",
    ClaimKind.TRAINING_CONSENT: "Set",
}


@dataclass(frozen=True)
class DraftInstrument:
    """A proposed instrument awaiting human countersignature. Not a claim."""

    draft_id: str
    asset_id: str            # the asset whose chain has the gap
    claim_kind: ClaimKind
    odrl: dict               # ODRL 2.2 payload, ingest-mapper grammar
    summary: str             # human-readable diff for the approval UI
    drafted_from_hint: str   # negotiation_hint this instrument answers


class Negotiator:
    """Deterministic v1: verdict + deal terms in -> minimal instrument out."""

    def __init__(self, signer_did: str = "did:key:zdoctusCounterparty") -> None:
        self.signer_did = signer_did

    def draft_extension(self, verdict: GateVerdict, *, asset_id: str,
                        channels: list[str], territories: list[str],
                        until: dt.datetime | None = None,
                        kind: ClaimKind | None = None) -> DraftInstrument:
        """Turn a deny into an extension instrument naming the exact gap.

        The counterparty terms (kind, channels/territories/window) are inputs —
        they ARE the business deal — while the *shape* of the fix comes from
        the verdict. A verb-absent deny carries ``missing_claim_kind``; scope
        and window denies do not, so the caller states the instrument class.
        """
        if verdict.allowed:
            raise ValueError("nothing to negotiate: the action was allowed")
        if not channels or not territories:
            raise ValueError(
                "refusing to draft an instrument with empty channel or "
                "territory terms - that would grant nothing (fail-closed)")
        resolved = kind or verdict.missing_claim_kind
        if resolved is None:
            raise ValueError(
                f"{verdict.reason.value if verdict.reason else 'deny'} names no "
                "claim kind; pass kind= to say which instrument to negotiate")
        if resolved not in _ODRL_TYPE:
            raise ValueError(f"cannot negotiate a '{resolved.value}' instrument")
        until_iso = (until or _default_until()).isoformat().replace("+00:00", "Z")

        offer: dict = {
            "@context": "http://www.w3.org/ns/odrl.jsonld",
            "@type": _ODRL_TYPE[resolved],
            "uid": f"urn:doctus:draft:{asset_id}:{resolved.value}",
            "assigner": {"uid": self.signer_did},
            "permission": [{"action": "publish", "target": f"urn:doctus:asset:{asset_id}",
                            "constraint": [
                                {"leftOperand": "channel", "operator": "isSubsetOf",
                                 "rightOperand": channels},
                                {"leftOperand": "territory", "operator": "isSubsetOf",
                                 "rightOperand": territories},
                                {"leftOperand": "until", "operator": "lteq",
                                 "rightOperand": until_iso},
                            ]}],
        }
        return DraftInstrument(
            draft_id=offer["uid"],
            asset_id=asset_id,
            claim_kind=resolved,
            odrl=offer,
            summary=(f"{resolved.value} extension on '{asset_id}': publish "
                     f"@ {channels}/{territories} until {until_iso}\n"
                     f"cures: {verdict.reason.value} — {verdict.detail}"),
            drafted_from_hint=verdict.negotiation_hint or verdict.detail,
        )


def _default_until() -> dt.datetime:
    """Demo-default window: one year out, UTC."""
    return dt.datetime.now(dt.UTC).replace(microsecond=0) + dt.timedelta(days=365)
