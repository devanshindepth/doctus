"""Countersign ledger: human approval turns a draft into a graph-valid claim.

CONTEXT.md invariant 6: "Human countersigns instruments — the negotiation
agent may *draft* licenses/consents; only a human approval turns one into a
graph-valid signed claim." In the real deployment approval happens in a UI
under the studio's key; for P3 this stub is the seam that UI will call. It is
deliberately boring and completely auditable:

- ``propose``  registers a DraftInstrument as PENDING (idempotent by draft_id);
- ``approve``  flips it to APPROVED (recorded approver + UTC instant), writes
               the claim into the rights graph, bumps graph_version, and
               invalidates compiled permissions so the next gate check
               recompiles;
- every transition lands in ``countersign_log`` — the human-approval leg of
  the insurer artifact.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

from doctus.agents.negotiator import DraftInstrument
from doctus.engine.models import ClaimKind
from doctus.graph.store import RightsGraph

_LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS countersign_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    action     TEXT NOT NULL,          -- PROPOSE | APPROVE
    draft_id   TEXT NOT NULL,
    asset_id   TEXT NOT NULL,
    kind       TEXT NOT NULL,
    odrl_json  TEXT NOT NULL,
    summary    TEXT NOT NULL,
    actor      TEXT,                   -- proposed_by / approving human
    claim_id   TEXT                    -- set on APPROVE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_countersign_once
    ON countersign_log(action, draft_id);
"""


def ensure_ledger(db: sqlite3.Connection) -> None:
    db.executescript(_LEDGER_SCHEMA)


class DraftNotProposedError(ValueError):
    """Approval attempted for a draft that never entered the ledger."""


class AlreadyApprovedError(ValueError):
    """Double-signing an instrument must be loud (one approval, one claim)."""


class CountersignLedger:
    """The human-approval seam between negotiation and the rights graph."""

    def __init__(self, graph: RightsGraph) -> None:
        self.graph = graph
        ensure_ledger(graph._db)

    # ------------------------------------------------------------------ API
    def propose(self, draft: DraftInstrument, *, proposed_by: str) -> str:
        """Register a draft as PENDING. Re-proposing an identical draft is a no-op."""
        try:
            self.graph._db.execute(
                "INSERT INTO countersign_log(ts, action, draft_id, asset_id,"
                " kind, odrl_json, summary, actor) VALUES (?,?,?,?,?,?,?,?)",
                (_utcnow().isoformat(), "PROPOSE", draft.draft_id, draft.asset_id,
                 draft.claim_kind.value, json.dumps(draft.odrl, sort_keys=True),
                 draft.summary, proposed_by))
            self.graph._db.commit()
        except sqlite3.IntegrityError:
            pass  # already proposed; idempotent
        return draft.draft_id

    def approve(self, draft: DraftInstrument, *, approver: str) -> str:
        """Record human approval, write the claim, invalidate stale permissions.

        Returns the new claim id. Raises if the draft was never proposed or was
        already approved — double-signing an instrument must be loud.
        """
        pending = self.graph._db.execute(
            "SELECT COUNT(*) FROM countersign_log"
            " WHERE action='PROPOSE' AND draft_id=?", (draft.draft_id,)).fetchone()[0]
        if not pending:
            raise DraftNotProposedError(
                f"draft '{draft.draft_id}' was never proposed")
        already = self.graph._db.execute(
            "SELECT COUNT(*) FROM countersign_log"
            " WHERE action='APPROVE' AND draft_id=?", (draft.draft_id,)).fetchone()[0]
        if already:
            raise AlreadyApprovedError(
                f"draft '{draft.draft_id}' was already approved - one approval, "
                "one claim")
        self.graph._db.execute(
            "INSERT INTO countersign_log(ts, action, draft_id, asset_id,"
            " kind, odrl_json, summary, actor) VALUES (?,?,?,?,?,?,?,?)",
            (_utcnow().isoformat(), "APPROVE", draft.draft_id, draft.asset_id,
             draft.claim_kind.value, json.dumps(draft.odrl, sort_keys=True),
             draft.summary, approver))

        claim_id = _claim_id_for(draft)
        from doctus.engine.models import Claim, Scope  # noqa: PLC0415
        scope = _scope_from_odrl(draft.odrl)
        self.graph.add_claim(Claim(
            claim_id=claim_id,
            kind=ClaimKind(draft.claim_kind.value),
            asset_id=draft.asset_id,
            signer=approver,
            trusted=True,
            issued_at=_utcnow(),
            valid_until=scope.valid_until if scope else None,
            scope=scope,
            odrl=draft.odrl,
        ))
        self.graph.invalidate_permissions(draft.asset_id)
        self.graph._db.execute(
            "UPDATE countersign_log SET claim_id=?"
            " WHERE action='APPROVE' AND draft_id=?", (claim_id, draft.draft_id))
        self.graph._db.commit()
        return claim_id

    # --------------------------------------------------------------- reads
    def pending(self) -> list[dict]:
        rows = self.graph._db.execute(
            "SELECT * FROM countersign_log WHERE action='PROPOSE' AND draft_id NOT IN"
            " (SELECT draft_id FROM countersign_log WHERE action='APPROVE')"
            " ORDER BY log_id").fetchall()
        return [dict(r) for r in rows]

    def history(self) -> list[dict]:
        rows = self.graph._db.execute(
            "SELECT * FROM countersign_log ORDER BY log_id").fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------- helpers
def _claim_id_for(draft: DraftInstrument) -> str:
    digest = hashlib.sha256(
        f"{draft.draft_id}|{json.dumps(draft.odrl, sort_keys=True)}".encode()
    ).hexdigest()[:10]
    return f"cs-{digest}"


def _scope_from_odrl(odrl: dict):
    """Mirror the ingest mapper's constraint grammar (graph/ingest.py)."""
    from doctus.engine.scope import Scope  # noqa: PLC0415

    channels: set[str] = set()
    territories: set[str] = set()
    valid_until = None
    for permission in odrl.get("permission", []) or []:
        for constraint in permission.get("constraint", []) or []:
            lo, op, ro = (constraint.get("leftOperand"),
                          constraint.get("operator"),
                          constraint.get("rightOperand"))
            if lo == "channel" and op == "isSubsetOf" and isinstance(ro, list):
                channels.update(ro)
            elif lo == "territory" and op == "isSubsetOf" and isinstance(ro, list):
                territories.update(ro)
            elif lo == "until" and op == "lteq" and isinstance(ro, str):
                parsed = _parse_time(ro)
                if parsed is not None:
                    valid_until = parsed if valid_until is None else min(valid_until, parsed)
    return Scope(channels=frozenset(channels), territories=frozenset(territories),
                 valid_until=valid_until)


def _parse_time(value: str):
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(microsecond=0)
