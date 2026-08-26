"""P3 agent layer: production tools behind the gate, negotiator, countersign.

- ``ProductionAgent``  generate/composite sign real C2PA media; every
  side-effectful verb routes through the ClearanceGate first.
- ``Negotiator``       turns deny verdicts into draft instruments; never signs.
- ``CountersignLedger`` human approval seam: draft -> graph-valid claim.
"""
from doctus.agents.countersign import (AlreadyApprovedError, CountersignLedger,
                                       DraftNotProposedError, ensure_ledger)
from doctus.agents.negotiator import DraftInstrument, Negotiator
from doctus.agents.production import ProductionAgent, ToolResult

__all__ = [
    "AlreadyApprovedError",
    "CountersignLedger",
    "DraftInstrument",
    "DraftNotProposedError",
    "Negotiator",
    "ProductionAgent",
    "ToolResult",
    "ensure_ledger",
]
