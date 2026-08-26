"""Decision-log reader + deterministic audit-report renderer (invariant 5).

The decisions table is the insurer/E&O artifact (CONTEXT.md §5): every row
links action -> claims evaluated -> outcome, so an auditor can replay exactly
why the gate allowed or denied a proposed action.

Rendering is deterministic: same rows => byte-identical report. Timestamps are
printed as stored (no re-formatting), claim lists keep insertion order, and
counts come from the data itself.
"""
from __future__ import annotations

import json
from typing import Any


def render_report(decisions: list[dict], *, title: str = "Doctus decision log") -> str:
    """Human-readable audit trail; byte-stable for identical input."""
    lines: list[str] = [f"# {title}", ""]
    if not decisions:
        lines += ["(no decisions recorded)", ""]
        return "\n".join(lines)

    allows = sum(1 for d in decisions if d["allowed"])
    denies = len(decisions) - allows
    lines.append(f"{len(decisions)} decision(s): {allows} allow, {denies} deny")
    lines.append("")
    for d in decisions:
        outcome = "ALLOW" if d["allowed"] else f"DENY {d['reason']}"
        head = (f"[{d['decision_id']}] {d['ts']}  {d['verb']} {d['asset_id']}"
                f"{_target_suffix(d)}  ->  {outcome}")
        lines.append(head)
        if d.get("detail"):
            lines.append(f"    detail: {d['detail']}")
        if d.get("negotiation_hint"):
            lines.append(f"    fix path: {d['negotiation_hint']}")
        for ref in _claim_refs(d):
            lines.append(f"    claim: {ref}")
        lines.append(f"    graph_version_at_check: {d['permissions_version']}")
        lines.append("")
    return "\n".join(lines)


def to_jsonl(decisions: list[dict]) -> str:
    """Machine-readable mirror of the report (one JSON object per line)."""
    return "\n".join(json.dumps(d, sort_keys=True) for d in decisions)


def summarize(decisions: list[dict]) -> dict[str, Any]:
    """Aggregates for the ClickHouse partner dashboard (DESIGN.md §3.5)."""
    by_reason: dict[str, int] = {}
    by_asset: dict[str, int] = {}
    for d in decisions:
        if not d["allowed"]:
            reason = d["reason"] or "UNKNOWN"
            by_reason[reason] = by_reason.get(reason, 0) + 1
        by_asset[d["asset_id"]] = by_asset.get(d["asset_id"], 0) + 1
    return {
        "total": len(decisions),
        "allows": sum(1 for d in decisions if d["allowed"]),
        "denies": len(decisions) - sum(1 for d in decisions if d["allowed"]),
        "deny_reasons": dict(sorted(by_reason.items())),
        "decisions_per_asset": dict(sorted(by_asset.items())),
    }


# ------------------------------------------------------------------ internals
def _target_suffix(d: dict) -> str:
    parts = []
    if d.get("channel"):
        parts.append(f"channel={d['channel']}")
    if d.get("territory"):
        parts.append(f"territory={d['territory']}")
    return f" ({', '.join(parts)})" if parts else ""


def _claim_refs(d: dict) -> list[str]:
    claims = d.get("claims_evaluated_json") or {}
    refs = []
    for c in claims.get("claims", []):
        trust = "" if c["trusted"] else " UNTRUSTED"
        refs.append(f"{c['claim_id']} [{c['kind']}] on {c['asset_id']}"
                    f" (signer {c['signer']}){trust}")
    return refs
