"""Production agent: generative tools whose side effects route through the gate.

DESIGN.md §3.4. The LLM may *propose* actions; only valid signed credentials
*authorize* them (CONTEXT.md §1). ``generate`` and ``composite`` are the only
ways assets enter the graph — each wraps its output in a real signed C2PA
manifest, so ingest stays on the P1 trust path — while every side-effectful
verb goes through ``ClearanceGate.check`` first and the agent sees deny reasons
verbatim (it learns to route around gaps legally; it cannot prompt-fuzz a
deterministic gate).

The agent is deliberately model-free in v1: an offline scripted policy stands
in for the Gemini/ADK planner until P4 wires the real cloud loop. The seam it
exposes — propose -> verdict -> act/deny — is exactly what an ADK tool wrapper
will call.
"""
from __future__ import annotations

from dataclasses import dataclass

from doctus.engine.gate import ClearanceGate
from doctus.engine.models import GateVerdict, ProposedAction, Verb
from doctus.graph.store import RightsGraph


@dataclass(frozen=True)
class ToolResult:
    """What a tool call returns to the planning model."""

    ok: bool
    tool: str
    asset_id: str | None = None
    detail: str = ""
    verdict: GateVerdict | None = None   # set on publish


class ProductionAgent:
    """Scripted stand-in for the ADK production agent (P3); tools == future ADK tools."""

    def __init__(self, graph: RightsGraph, gate: ClearanceGate,
                 signer_cert_pem: bytes | None = None,
                 signer_key_pem: bytes | None = None) -> None:
        self.graph = graph
        self.gate = gate
        self._cert = signer_cert_pem
        self._key = signer_key_pem

    # ------------------------------------------------------------ beat 1/2
    def generate(self, *, src_media: str, out_path: str, asset_id: str,
                 label: str = "", model: str = "veo-3.0-demo") -> ToolResult:
        """Create a new signed generation asset and register it in the graph.

        Real signing requires studio PKI material; without it the call fails
        closed with guidance rather than producing an unsigned asset.
        """
        if self._cert is None or self._key is None:
            return ToolResult(ok=False, tool="generate", detail=(
                "no signer material loaded; generate() signs real C2PA media "
                "and refuses to create unmanifested assets"))
        from doctus.agents.signing import sign_media  # noqa: PLC0415

        sign_media(src_media, out_path, cert_pem=self._cert, key_pem=self._key,
                   asset_id=asset_id, label=label or asset_id,
                   generation_model=model)
        return ToolResult(ok=True, tool="generate", asset_id=asset_id,
                          detail=f"signed manifest written to {out_path}")

    # ------------------------------------------------------------ beat 3
    def composite(self, *, src_media: str, out_path: str, asset_id: str,
                  ingredients: list[tuple[str, str]], label: str = "",
                  model: str = "doctus-compositor-v1") -> ToolResult:
        """Composite ingredient assets into a new signed asset + graph edges."""
        if self._cert is None or self._key is None:
            return ToolResult(ok=False, tool="composite", detail=(
                "no signer material loaded; composite() signs real C2PA media "
                "and refuses to create unmanifested assets"))
        from doctus.agents.signing import sign_media  # noqa: PLC0415

        sign_media(src_media, out_path, cert_pem=self._cert, key_pem=self._key,
                   asset_id=asset_id, label=label or asset_id,
                   generation_model=model,
                   ingredients=[(title, path) for title, path in ingredients])
        return ToolResult(ok=True, tool="composite", asset_id=asset_id,
                          detail=f"signed composite written to {out_path} "
                                 f"with ingredients {[t for t, _ in ingredients]}")

    # ------------------------------------------------- beats 4+5 (the gate)
    def publish(self, *, asset_id: str, channel: str, territory: str,
                expected_graph_version: int | None = None) -> ToolResult:
        """Side-effectful verb: DENY comes back as data, never an exception."""
        action = ProposedAction(verb=Verb.PUBLISH, asset_id=asset_id,
                                channel=channel, territory=territory,
                                expected_graph_version=expected_graph_version)
        verdict = self.gate.check(action)
        return ToolResult(
            ok=verdict.allowed, tool="publish", asset_id=asset_id,
            detail=(verdict.detail if not verdict.allowed else "allowed"),
            verdict=verdict)

    def check_permission(self, verb: Verb, asset_id: str, *,
                         channel: str | None = None,
                         territory: str | None = None) -> GateVerdict:
        """Ask-before-acting form of the gate for planners that preflight."""
        return self.gate.check(ProposedAction(
            verb=verb, asset_id=asset_id, channel=channel, territory=territory))
