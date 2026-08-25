"""Materialized effective permissions per asset (compile-on-write, lookup-at-read)."""
from __future__ import annotations

import sqlite3

_TABLE = """
CREATE TABLE IF NOT EXISTS effective_permissions (
    asset_id          TEXT PRIMARY KEY,
    graph_version     INTEGER NOT NULL,
    compiled_at       TEXT NOT NULL,
    policy_version    TEXT NOT NULL,
    permissions_json  TEXT NOT NULL,
    constraints_hash  TEXT NOT NULL
);
"""


def ensure_table(db: sqlite3.Connection) -> None:
    db.executescript(_TABLE)


def upsert(db: sqlite3.Connection, asset_id: str, graph_version: int, compiled_at: str,
           policy_version: str, permissions_json: str, constraints_hash: str) -> None:
    ensure_table(db)
    db.execute(
        "INSERT OR REPLACE INTO effective_permissions(asset_id, graph_version, compiled_at,"
        " policy_version, permissions_json, constraints_hash) VALUES (?,?,?,?,?,?)",
        (asset_id, graph_version, compiled_at, policy_version, permissions_json,
         constraints_hash),
    )
    db.commit()
