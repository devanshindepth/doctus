"""Rights Graph store: assets, ingredient edges, claims, decisions, permissions.

SQLite behind a repository interface (CONTEXT.md §3.5) so ClickHouse can mirror
without touching callers. Every mutation bumps graph_version.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from doctus.engine.models import AssetRecord, Claim, IngredientEdge

_SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    label    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    asset_id      TEXT NOT NULL REFERENCES assets(asset_id),
    ingredient_id TEXT NOT NULL REFERENCES assets(asset_id),
    PRIMARY KEY (asset_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id    TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    asset_id    TEXT NOT NULL REFERENCES assets(asset_id),
    signer      TEXT NOT NULL,
    trusted     INTEGER NOT NULL,
    issued_at   TEXT NOT NULL,
    valid_from  TEXT,
    valid_until TEXT,
    scope_json  TEXT,
    odrl_json   TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO meta(key, value) VALUES ('graph_version', '0');

CREATE TABLE IF NOT EXISTS decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    asset_id    TEXT NOT NULL,
    verb        TEXT NOT NULL,
    channel     TEXT,
    territory   TEXT,
    allowed     INTEGER NOT NULL,
    reason      TEXT,
    detail      TEXT,
    claims_evaluated_json TEXT,
    action_json TEXT,
    negotiation_hint TEXT,
    permissions_version INTEGER
);
"""


class RightsGraph:
    """Persistence + versioning for the rights graph."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)

    # -- reads -------------------------------------------------------------
    @property
    def graph_version(self) -> int:
        row = self._db.execute("SELECT value FROM meta WHERE key='graph_version'").fetchone()
        return int(row["value"])

    def get_asset(self, asset_id: str) -> AssetRecord | None:
        row = self._db.execute(
            "SELECT asset_id, label FROM assets WHERE asset_id=?", (asset_id,)
        ).fetchone()
        return AssetRecord(**dict(row)) if row else None

    def claims_for(self, asset_ids: list[str]) -> list[Claim]:
        if not asset_ids:
            return []
        marks = ",".join("?" * len(asset_ids))
        rows = self._db.execute(
            f"SELECT * FROM claims WHERE asset_id IN ({marks})", asset_ids
        ).fetchall()
        return [self._row_to_claim(r) for r in rows]

    def ingredients_of(self, asset_id: str) -> list[str]:
        rows = self._db.execute(
            "SELECT ingredient_id FROM edges WHERE asset_id=?", (asset_id,)
        ).fetchall()
        return [r["ingredient_id"] for r in rows]

    def ancestor_closure(self, asset_id: str) -> tuple[list[str], bool]:
        """BFS over ingredient edges. Returns (ids including root, acyclic)."""
        seen: list[str] = []
        queue = [asset_id]
        while queue:
            current = queue.pop(0)
            if current in seen:
                return seen, False          # cycle => refuse to compile (fail-closed upstream)
            seen.append(current)
            queue.extend(i for i in self.ingredients_of(current) if i not in seen)
        return seen, True

    def latest_permissions(self, asset_id: str) -> "sqlite3.Row | None":  # type: ignore[name-defined]
        from doctus.engine.permissions_store import ensure_table  # noqa: PLC0415
        ensure_table(self._db)
        return self._db.execute(
            "SELECT * FROM effective_permissions WHERE asset_id=? ORDER BY compiled_at DESC LIMIT 1",
            (asset_id,),
        ).fetchone()

    def record_decision(self, ts: str, asset_id: str, verb: str, allowed: bool,
                        reason: str | None, detail: str | None,
                        permissions_version: int | None,
                        channel: str | None = None,
                        territory: str | None = None,
                        claims_evaluated_json: str | None = None,
                        action_json: str | None = None,
                        negotiation_hint: str | None = None) -> int:
        """Append one audit row (invariant 5): action -> claims evaluated -> outcome."""
        import json as _json  # noqa: PLC0415

        cur = self._db.execute(
            "INSERT INTO decisions(ts, asset_id, verb, channel, territory, allowed,"
            " reason, detail, claims_evaluated_json, action_json, negotiation_hint,"
            " permissions_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (ts, asset_id, verb, channel, territory, int(allowed), reason, detail,
             claims_evaluated_json, action_json, negotiation_hint,
             permissions_version),
        )
        self._db.commit()
        return int(cur.lastrowid)

    def decisions_for(self, asset_id: str) -> list[dict]:
        """Read back the audit trail for one asset, oldest first."""
        rows = self._db.execute(
            "SELECT * FROM decisions WHERE asset_id=? ORDER BY decision_id",
            (asset_id,),
        ).fetchall()
        return [_decision_row_to_dict(r) for r in rows]

    def all_decisions(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT * FROM decisions ORDER BY decision_id").fetchall()
        return [_decision_row_to_dict(r) for r in rows]

    # -- writes ------------------------------------------------------------
    def add_asset(self, record: AssetRecord) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO assets(asset_id, label) VALUES (?,?)",
            (record.asset_id, record.label),
        )
        self._bump()

    def add_claim(self, claim: Claim) -> None:
        import json as _json  # noqa: PLC0415

        scope_json = _json.dumps(_scope_to_dict(claim.scope)) if claim.scope is not None else None
        self._db.execute(
            "INSERT OR REPLACE INTO claims(claim_id, kind, asset_id, signer, trusted,"
            " issued_at, valid_from, valid_until, scope_json, odrl_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                claim.claim_id, claim.kind.value, claim.asset_id, claim.signer,
                int(claim.trusted), claim.issued_at.isoformat(),
                claim.valid_from.isoformat() if claim.valid_from else None,
                claim.valid_until.isoformat() if claim.valid_until else None,
                scope_json,
                _json.dumps(claim.odrl, sort_keys=True) if claim.odrl else None,
            ),
        )
        self._bump()

    def add_edge(self, edge: IngredientEdge) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO edges(asset_id, ingredient_id) VALUES (?,?)",
            (edge.asset_id, edge.ingredient_id),
        )
        self._bump()

    def invalidate_permissions(self, asset_id: str | None = None) -> None:
        from doctus.engine.permissions_store import ensure_table  # noqa: PLC0415
        ensure_table(self._db)
        if asset_id is None:
            self._db.execute("DELETE FROM effective_permissions")
        else:
            self._db.execute("DELETE FROM effective_permissions WHERE asset_id=?", (asset_id,))
        self._db.commit()

    def _bump(self) -> None:
        self._db.execute(
            "UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='graph_version'"
        )
        self._db.commit()

    @staticmethod
    def _row_to_claim(r: sqlite3.Row) -> Claim:
        import json as _json  # noqa: PLC0415

        from doctus.engine.models import ClaimKind  # noqa: PLC0415
        from doctus.engine.scope import Scope  # noqa: PLC0415

        scope = None
        if r["scope_json"]:
            d = _json.loads(r["scope_json"])
            scope = Scope(
                channels=frozenset(d.get("channels", [])),
                territories=frozenset(d.get("territories", [])),
                valid_until=(dt_from_iso(d["valid_until"]) if d.get("valid_until") else None),
                exclusions=frozenset(d.get("exclusions", [])),
                unlimited=bool(d.get("unlimited", False)),
            )
        return Claim(
            claim_id=r["claim_id"],
            kind=ClaimKind(r["kind"]),
            asset_id=r["asset_id"],
            signer=r["signer"],
            trusted=bool(r["trusted"]),
            issued_at=dt_from_iso(r["issued_at"]),
            valid_from=dt_from_iso(r["valid_from"]) if r["valid_from"] else None,
            valid_until=dt_from_iso(r["valid_until"]) if r["valid_until"] else None,
            scope=scope,
            odrl=_json.loads(r["odrl_json"]) if r["odrl_json"] else {},
        )


def dt_from_iso(value: str) -> __import__("datetime").datetime:  # noqa: F401
    import datetime as _dt  # noqa: PLC0415

    return _dt.datetime.fromisoformat(value)


_DECISION_COLUMNS = (
    "decision_id", "ts", "asset_id", "verb", "channel", "territory", "allowed",
    "reason", "detail", "claims_evaluated_json", "action_json",
    "negotiation_hint", "permissions_version",
)


def _decision_row_to_dict(r: sqlite3.Row) -> dict:
    import json as _json  # noqa: PLC0415

    d = {col: r[col] for col in _DECISION_COLUMNS}
    for key in ("claims_evaluated_json", "action_json"):
        if d.get(key):
            d[key] = _json.loads(d[key])
    return d


def _scope_to_dict(scope) -> dict:
    return {
        "channels": sorted(scope.channels),
        "territories": sorted(scope.territories),
        "valid_until": scope.valid_until.isoformat() if scope.valid_until else None,
        "exclusions": sorted(scope.exclusions),
        "unlimited": scope.unlimited,
    }
