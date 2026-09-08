"""CloudStudio: the wired studio the ADK agent runs inside (P4).

One object assembling the whole stack from a CloudConfig:

  ShotBackend -> ProductionAgent.generate/composite -> ManifestIngester
                -> RightsGraph -> PolicyCompiler -> ClearanceGate
                -> Negotiator + CountersignLedger

The P4 seam contract with the agent plane (DESIGN.md §3.4): every method is a
unit that returns plain data - verdicts, reports, summaries - and NEVER raises
on deny. Denials are results, not exceptions; only configuration and integrity
problems raise.
"""
from __future__ import annotations

from pathlib import Path

from doctus.agents.countersign import CountersignLedger
from doctus.agents.negotiator import DraftInstrument, Negotiator
from doctus.agents.production import ProductionAgent, ToolResult
from doctus.cloud.config import CloudConfig
from doctus.cloud.veo import shot_backend_from_config
from doctus.engine.compiler import PolicyCompiler
from doctus.engine.gate import ClearanceGate
from doctus.engine.models import ClaimKind, GateVerdict, Verb
from doctus.graph.ingest import ManifestIngester
from doctus.graph.store import RightsGraph


class CloudStudio:
    """Assembled production environment behind the ADK tool wrappers."""

    def __init__(self, graph: RightsGraph, *, agent: ProductionAgent,
                 ingester: ManifestIngester, gate: ClearanceGate,
                 ledger: CountersignLedger, config: CloudConfig,
                 backend) -> None:
        self.graph = graph
        self.agent = agent
        self.ingester = ingester
        self.gate = gate
        self.ledger = ledger
        self.config = config
        self.backend = backend

    # ------------------------------------------------------------------ setup
    @classmethod
    def create(cls, *, db_path: str | Path = ":memory:",
               media_dir: Path | None = None,
               pki_dir: Path | None = None,
               config: CloudConfig | None = None) -> "CloudStudio":
        """Build the full stack. Defaults to the committed demo PKI/media."""
        repo = Path(__file__).resolve().parents[3]
        pki = pki_dir or repo / "fixtures" / "pki"
        anchor = pki / "demo_root.pem"
        if not anchor.exists():
            raise RuntimeError(
                f"trust anchor missing at {anchor} - run scripts/prebake_fixtures.py")
        cfg = config or CloudConfig.from_env()
        g = RightsGraph(str(db_path))
        ingester = ManifestIngester(g, trust_anchors_pem=anchor.read_text(encoding="utf-8"))
        if media_dir is not None:
            ingester.ingest_directory(media_dir)
        gate = ClearanceGate(g, PolicyCompiler(g))
        cert = (pki / "demo_signer.pem").read_bytes()
        key = (pki / "demo_signer.key").read_bytes()
        agent = ProductionAgent(g, gate, signer_cert_pem=cert, signer_key_pem=key)
        return cls(graph=g, agent=agent, ingester=ingester, gate=gate,
                   ledger=CountersignLedger(g), config=cfg,
                   backend=shot_backend_from_config(cfg))

    @property
    def graph_version(self) -> int:
        return self.graph.current_graph_version()

    # ------------------------------------------------------------------ tools
    def generate_shot(self, *, asset_id: str, prompt: str, workdir: Path,
                      label: str = "") -> dict:
        """Beat 1 end-to-end: fetch raw shot (backend-dependent), sign, ingest."""
        raw = self.backend.fetch(prompt=prompt, out_path=workdir / f"_raw_{asset_id}.jpg")
        out_path = workdir / f"{asset_id}.jpg"
        result = self.agent.generate(src_media=str(raw), out_path=str(out_path),
                                     asset_id=asset_id, label=label or prompt[:60])
        return self._ingest_result("generate", result, out_path)

    def composite(self, *, asset_id: str, ingredients: list[tuple[str, str]],
                  workdir: Path, label: str = "") -> dict:
        """Beat 3 end-to-end: sign a composite over ingredient assets, ingest."""
        raw = self.backend.fetch(prompt=label or "composite",
                                 out_path=workdir / f"_raw_{asset_id}.jpg")
        out_path = workdir / f"{asset_id}.jpg"
        result = self.agent.composite(src_media=str(raw), out_path=str(out_path),
                                      asset_id=asset_id, label=label or asset_id,
                                      ingredients=ingredients)
        return self._ingest_result("composite", result, out_path)

    def publish(self, *, asset_id: str, channel: str, territory: str,
                expected_graph_version: int | None = None) -> dict:
        """Gate-routed side-effectful verb. Returns verdict-as-dict, never raises on deny."""
        result: ToolResult = self.agent.publish(
            asset_id=asset_id, channel=channel, territory=territory,
            expected_graph_version=expected_graph_version)
        v = result.verdict
        assert v is not None  # publish always carries a verdict
        return _verdict_dict(v)

    def draft_extension(self, verdict: dict, *, asset_id: str,
                        channels: list[str], territories: list[str],
                        until=None, kind: str | None = None) -> DraftInstrument:
        """Negotiator leg: deny-verdict payload -> proposed instrument."""
        kind_enum = ClaimKind(kind) if kind else None
        return Negotiator().draft_extension(
            _verdict_obj(verdict), asset_id=asset_id, channels=channels,
            territories=territories, until=until, kind=kind_enum)

    def countersign_approve(self, draft: DraftInstrument, *, approver: str) -> str:
        """Human seam: write the approved claim into the graph. Returns claim id."""
        self.ledger.propose(draft, proposed_by="negotiator-v1")
        return self.ledger.approve(draft, approver=approver)

    def pending_drafts(self) -> list[dict]:
        return self.ledger.pending()

    def propose_draft(self, draft: DraftInstrument, *, proposed_by: str = "adk-agent") -> str:
        """Register an agent-drafted instrument as PENDING for human approval.

        Proposing writes a queue row only - invariant 6 keeps approval human.
        """
        return self.ledger.propose(draft, proposed_by=proposed_by)

    def check_permission(self, verb: str, asset_id: str, *, channel=None,
                         territory=None) -> dict:
        """Preflight form of the gate for planners that ask before acting."""
        return _verdict_dict(self.agent.check_permission(
            Verb(verb), asset_id, channel=channel, territory=territory))

    # --------------------------------------------------------------- internals
    def _ingest_result(self, tool: str, result: ToolResult, out_path: Path) -> dict:
        if not result.ok:
            return {"ok": False, "tool": tool, "detail": result.detail}
        report = self.ingester.ingest_file(out_path)
        return {
            "ok": bool(report.trusted),
            "tool": tool,
            "asset_id": report.asset_id,
            "media": str(out_path),
            "ingest_status": report.status,
            "trusted": bool(report.trusted),
            "claims": len(report.claim_ids),
            "edges": [list(e) for e in getattr(report, "edges", [])],
            "detail": result.detail,
        }


def _verdict_dict(v: GateVerdict) -> dict:
    return {
        "allowed": v.allowed,
        "verb": v.verb.value,
        "asset_id": v.asset_id,
        "reason": v.reason.value if v.reason else None,
        "detail": v.detail,
        "negotiation_hint": v.negotiation_hint,
        "missing_claim_kind": v.missing_claim_kind.value if v.missing_claim_kind else None,
        "decision_id": v.decision_id,
    }


def _verdict_obj(payload: dict) -> GateVerdict:
    """Rehydrate the minimal fields Negotiator.draft_extension reads."""
    from doctus.engine.models import DenyReason  # noqa: PLC0415

    reason = payload.get("reason")
    return GateVerdict(
        allowed=bool(payload.get("allowed")),
        asset_id=payload.get("asset_id", ""),
        verb=Verb(payload.get("verb") or "publish"),
        reason=DenyReason(reason) if reason else None,
        detail=payload.get("detail", ""),
        negotiation_hint=payload.get("negotiation_hint"),
    )
