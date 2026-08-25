"""Golden fixture harness: load YAML cases, replay actions, assert verdicts.

A case file defines a small rights graph plus the expected compiled permissions
and gate verdicts. CI runs every case; a byte-stable report is emitted for
regression diffs.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from doctus.engine.compiler import PolicyCompiler
from doctus.engine.gate import ClearanceGate
from doctus.engine.models import (AssetRecord, Claim, ClaimKind, ProposedAction,
                                  Verb)
from doctus.engine.scope import Scope
from doctus.graph.store import RightsGraph

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "cases"


def _ts(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value) if value else None


def build_graph(case: dict) -> tuple[RightsGraph, PolicyCompiler]:
    g = RightsGraph(":memory:")
    for asset in case["assets"]:
        g.add_asset(AssetRecord(asset_id=asset["id"], label=asset.get("label", "")))
    for edge in case.get("edges", []):
        g.add_edge_ingredient(edge["asset"], edge["ingredient"])
    for c in case["claims"]:
        scope = None
        if c.get("scope"):
            s = c["scope"]
            scope = Scope(
                channels=frozenset(s.get("channels", [])),
                territories=frozenset(s.get("territories", [])),
                valid_until=_ts(s.get("valid_until")),
                exclusions=frozenset(s.get("exclusions", [])),
                unlimited=bool(s.get("unlimited", False)),
            )
        g.add_claim(Claim(
            claim_id=c["claim_id"],
            kind=ClaimKind(c["kind"]),
            asset_id=c["asset"],
            signer=c.get("signer", "unknown"),
            trusted=bool(c.get("trusted", True)),
            issued_at=_ts(c["issued_at"]),
            valid_from=_ts(c.get("valid_from")),
            valid_until=_ts(c.get("valid_until")),
            scope=scope,
        ))
    return g, PolicyCompiler(g)


def run_case(path: Path) -> list[str]:
    """Execute one case. Returns list of failures (empty == pass)."""
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    now = dt.datetime.fromisoformat(case["now"])
    graph, compiler = build_graph(case)
    gate = ClearanceGate(graph, compiler, now_fn=lambda tz: now)
    failures: list[str] = []

    for action in case.get("actions", []):
        verdict = gate.check(ProposedAction(
            verb=Verb(action["verb"]),
            asset_id=action["asset"],
            channel=action.get("channel"),
            territory=action.get("territory"),
            expected_graph_version=action.get("expected_graph_version"),
        ))
        expect = action["expect"]
        if verdict.allowed != expect["allowed"]:
            failures.append(
                f"{path.name}:{action['name']} allowed={verdict.allowed} "
                f"(want {expect['allowed']}) reason={verdict.reason} detail={verdict.detail}")
            continue
        if not expect["allowed"]:
            want_reason = expect.get("reason")
            if want_reason and verdict.reason is not None and \
                    verdict.reason.value != want_reason:
                failures.append(
                    f"{path.name}:{action['name']} reason={verdict.reason.value} "
                    f"(want {want_reason})")
        if expect.get("detail_contains") and \
                expect["detail_contains"] not in verdict.detail:
            failures.append(
                f"{path.name}:{action['name']} detail={verdict.detail!r} "
                f"missing '{expect['detail_contains']}'")

    # every deny must explain itself (CONTEXT invariant 3)
    for record in graph._db.execute(
            "SELECT * FROM decisions WHERE allowed=0").fetchall():
        if not record["reason"] or not record["detail"]:
            failures.append(f"{path.name}: deny row {record['decision_id']} lacks explanation")

    # mid-case countersign simulation (demo arc): add claims, retry actions
    for c in case.get("post_claims", []):
        _add_claim(graph, c)
    for action in case.get("actions_after_post", []):
        verdict = gate.check(ProposedAction(
            verb=Verb(action["verb"]),
            asset_id=action["asset"],
            channel=action.get("channel"),
            territory=action.get("territory"),
        ))
        expect = action["expect"]
        if verdict.allowed != expect["allowed"]:
            failures.append(
                f"{path.name}:after:{action['name']} allowed={verdict.allowed} "
                f"(want {expect['allowed']}) reason={verdict.reason} detail={verdict.detail}")
    return failures


def _add_claim(graph: RightsGraph, c: dict) -> None:
    scope = None
    if c.get("scope"):
        s = c["scope"]
        scope = Scope(
            channels=frozenset(s.get("channels", [])),
            territories=frozenset(s.get("territories", [])),
            valid_until=_ts(s.get("valid_until")),
            exclusions=frozenset(s.get("exclusions", [])),
            unlimited=bool(s.get("unlimited", False)),
        )
    graph.add_claim(Claim(
        claim_id=c["claim_id"],
        kind=ClaimKind(c["kind"]),
        asset_id=c["asset"],
        signer=c.get("signer", "unknown"),
        trusted=bool(c.get("trusted", True)),
        issued_at=_ts(c["issued_at"]),
        valid_from=_ts(c.get("valid_from")),
        valid_until=_ts(c.get("valid_until")),
        scope=scope,
    ))


def all_cases() -> list[Path]:
    return sorted(FIXTURE_DIR.glob("*.yaml"))


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for path in all_cases():
        if run_case(path):
            failed += 1
        else:
            passed += 1
    return passed, failed
