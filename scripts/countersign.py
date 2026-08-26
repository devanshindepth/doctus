"""Countersign CLI stub (P3 deliverable, DESIGN.md §6): human approval seam.

The negotiation side registers PENDING drafts in the ledger; a human reviews
and approves them here. Approval writes the claim into the rights graph,
bumps graph_version, and invalidates compiled permissions, so the next gate
check recompiles — the deny->fix->allow loop closes.

Usage:
    python scripts/countersign.py --db scratch/p3_demo/doctus.db list
    python scripts/countersign.py --db scratch/p3_demo/doctus.db show <draft_id>
    python scripts/countersign.py --db scratch/p3_demo/doctus.db approve <draft_id> \
        --approver "Studio Lead"

In production this seam is a UI under the studio's signing key; the ledger
schema and calls are what that UI will use (CONTEXT.md invariant 6).
"""
from __future__ import annotations

import argparse
import json
import sys

from doctus.agents.countersign import AlreadyApprovedError, CountersignLedger, DraftNotProposedError
from doctus.agents.negotiator import DraftInstrument
from doctus.engine.models import ClaimKind
from doctus.graph.store import RightsGraph


def _rebuild_draft(row) -> DraftInstrument:
    return DraftInstrument(
        draft_id=row["draft_id"],
        asset_id=row["asset_id"],
        claim_kind=ClaimKind(row["kind"]),
        odrl=json.loads(row["odrl_json"]),
        summary=row["summary"],
        drafted_from_hint="",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="path to the Doctus SQLite graph DB")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show drafts awaiting approval")
    show = sub.add_parser("show", help="show one draft's full instrument")
    show.add_argument("draft_id")
    approve = sub.add_parser("approve", help="human-approves a draft -> signed claim")
    approve.add_argument("draft_id")
    approve.add_argument("--approver", required=True,
                         help="name of the approving human (recorded in the audit trail)")

    args = parser.parse_args(argv)
    ledger = CountersignLedger(RightsGraph(args.db))

    if args.command == "list":
        pending = ledger.pending()
        if not pending:
            print("no drafts awaiting approval")
            return 0
        for row in pending:
            print(f"{row['draft_id']}\n    asset={row['asset_id']} kind={row['kind']}"
                  f"\n    {row['summary']}")
        return 0

    if args.command == "show":
        matches = [h for h in ledger.history()
                   if h["draft_id"] == args.draft_id and h["action"] == "PROPOSE"]
        if not matches:
            print(f"unknown draft: {args.draft_id}", file=sys.stderr)
            return 1
        row = matches[-1]
        print(f"draft:   {row['draft_id']}")
        print(f"asset:   {row['asset_id']} ({row['kind']})")
        print(f"summary: {row['summary']}")
        print("instrument:")
        print(json.dumps(json.loads(row["odrl_json"]), indent=2))
        return 0

    # approve
    rows = [h for h in ledger.history()
            if h["draft_id"] == args.draft_id and h["action"] == "PROPOSE"]
    if not rows:
        print(f"unknown draft: {args.draft_id}", file=sys.stderr)
        return 1
    try:
        claim_id = ledger.approve(_rebuild_draft(rows[-1]), approver=args.approver)
    except (DraftNotProposedError, AlreadyApprovedError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(f"approved by {args.approver} -> claim {claim_id}")
    print("compiled permissions invalidated; the next gate check recompiles.")
    print("re-run the denied action to see it allowed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
