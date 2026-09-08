"""Doctus Studio Server: High-Performance Multi-Threaded REST API & UI Server.

Designed for non-technical users and hackathon judges to manage clearance,
run pre-flight checks, inspect C2PA provenance, approve countersignatures,
and execute demo scenarios.
"""
from __future__ import annotations

import datetime as dt
import http.server
import json
import os
import socketserver
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from doctus.agents.countersign import AlreadyApprovedError, CountersignLedger, DraftNotProposedError
from doctus.agents.negotiator import DraftInstrument
from doctus.analytics.clickhouse import ClickHouseConfig, ClickHouseMirror
from doctus.cloud.config import CloudConfig
from doctus.cloud.studio import CloudStudio
from doctus.cloud.tools import make_tools
from doctus.engine.models import AssetRecord, Claim, ClaimKind, IngredientEdge
from doctus.engine.scope import Scope
from doctus.graph.store import RightsGraph

MEDIA = REPO / "fixtures" / "media"
STATIC_DIR = Path(__file__).resolve().parent / "static"


class StudioEngine:
    """Stateful engine wrapping CloudStudio, ClickHouse, and Demo controller."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="doctus_studio_"))
        self.db_path = db_path or (self.workdir / "studio.db")
        self.cfg = CloudConfig.from_env()
        self.studio = CloudStudio.create(db_path=self.db_path, media_dir=MEDIA, config=self.cfg)
        self.mirror = ClickHouseMirror(ClickHouseConfig.from_env())
        self.demo_current_beat = 0
        self.demo_logs: list[dict[str, Any]] = []
        self._seed_initial_state()

    def _seed_initial_state(self) -> None:
        """Seed prebaked media assets so judges see a populated studio immediately."""
        self.mirror.sync_from_sqlite(self.studio.graph)

    def reset_demo(self) -> None:
        """Reset demo scenario to clean state."""
        self.demo_current_beat = 0
        self.demo_logs.clear()
        # Re-create studio DB
        if self.db_path.exists():
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        self.studio = CloudStudio.create(db_path=self.db_path, media_dir=MEDIA, config=self.cfg)
        self.mirror = ClickHouseMirror(ClickHouseConfig.from_env())
        self._seed_initial_state()
        self._log_demo_event(0, "RESET", "Studio state reset to clean baseline.")

    def _log_demo_event(self, beat: int, status: str, message: str, data: Any = None) -> None:
        event = {
            "beat": beat,
            "status": status,
            "message": message,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "data": data,
        }
        self.demo_logs.append(event)

    def run_beat(self, target_beat: int | None = None) -> dict[str, Any]:
        """Execute the next beat or a specific beat (1 to 8)."""
        beat = target_beat if target_beat is not None else (self.demo_current_beat + 1)
        if beat > 8:
            return {"ok": False, "message": "Demo arc already completed all 8 beats. Click reset to replay."}

        res: dict[str, Any] = {"beat": beat, "ok": True}

        if beat == 1:
            # Beat 1: Veo shot generation
            r = self.studio.generate_shot(
                asset_id="ast_veo_shot_demo",
                prompt="Cinematic shot of neon cyberpunk metropolis at midnight",
                workdir=self.workdir,
                label="Agent-generated Veo Shot",
            )
            res["result"] = r
            self._log_demo_event(1, "GENERATED", "Veo generated hero shot with signed C2PA manifest.", r)

        elif beat == 2:
            # Beat 2: Talent likeness publish on social
            v = self.studio.publish(asset_id="ast_talent_frame_v1", channel="social", territory="US")
            res["verdict"] = v
            self._log_demo_event(2, "ALLOWED" if v["allowed"] else "DENIED",
                                 "Talent likeness cleared for social distribution.", v)

        elif beat == 3:
            # Beat 3: Composite hero take + festival music bed
            r = self.studio.composite(
                asset_id="ast_composite_demo",
                ingredients=[
                    ("ast_hero_shot_v1", str(MEDIA / "ast_hero_shot_v1.jpg")),
                    ("ast_music_bed_v1", str(MEDIA / "ast_music_bed_v1.jpg")),
                ],
                workdir=self.workdir,
                label="Hero take + festival music bed",
            )
            res["result"] = r
            self._log_demo_event(3, "COMPOSITED", "Composited hero shot and festival-licensed music bed.", r)

        elif beat == 4:
            # Beat 4: Festival publish (ALLOWED)
            v = self.studio.publish(asset_id="ast_composite_demo", channel="festival", territory="US")
            res["verdict"] = v
            self._log_demo_event(4, "ALLOWED" if v["allowed"] else "DENIED",
                                 "Composite cleared for film festival distribution.", v)

        elif beat == 5:
            # Beat 5: Trailer publish (DENIED)
            v = self.studio.publish(asset_id="ast_composite_demo", channel="trailer", territory="US")
            res["verdict"] = v
            self._log_demo_event(5, "BLOCKED", "Clearance Gate blocked trailer release: SCOPE_EXCEEDED.", v)

        elif beat == 6:
            # Beat 6: Autonomous negotiation draft
            # Fetch latest deny verdict
            decisions = self.studio.graph.all_decisions()
            denies = [d for d in decisions if not d["allowed"] and d["asset_id"] == "ast_composite_demo"]
            latest_deny = denies[-1] if denies else {}
            tools = {fn.__name__: fn for fn in make_tools(self.studio)}
            proposal = tools["propose_license_extension"](
                verdict=latest_deny,
                asset_id="ast_music_bed_v1",
                channels=["trailer"],
                territories=["US"],
            )
            res["proposal"] = proposal
            self._log_demo_event(6, "PROPOSED", "Negotiator drafted ODRL license extension (awaiting human signature).", proposal)

        elif beat == 7:
            # Beat 7: Human Countersignature
            ledger = CountersignLedger(self.studio.graph)
            pending = ledger.pending()
            if not pending:
                res["ok"] = False
                res["message"] = "No pending draft found to countersign."
                return res
            target = pending[-1]
            draft = DraftInstrument(
                draft_id=target["draft_id"],
                asset_id=target["asset_id"],
                claim_kind=ClaimKind(target["kind"]),
                odrl=json.loads(target["odrl_json"]),
                summary=target["summary"],
                drafted_from_hint="",
            )
            claim_id = ledger.approve(draft, approver="Elena Vance (Studio Legal Lead)")
            res["claim_id"] = claim_id
            self._log_demo_event(7, "COUNTERSIGNED", f"Human Legal Lead approved and signed claim {claim_id}.", {"claim_id": claim_id})

        elif beat == 8:
            # Beat 8: Re-publish trailer (ALLOWED)
            v = self.studio.publish(asset_id="ast_composite_demo", channel="trailer", territory="US")
            res["verdict"] = v
            self._log_demo_event(8, "CLEARED", "Trailer publish re-checked and ALLOWED under new countersigned rights.", v)

        self.demo_current_beat = beat
        self.mirror.sync_from_sqlite(self.studio.graph)
        return res

    def get_summary(self) -> dict[str, Any]:
        self.mirror.sync_from_sqlite(self.studio.graph)
        summary = self.mirror.get_studio_executive_summary()
        ledger = CountersignLedger(self.studio.graph)
        summary["pending_approvals"] = len(ledger.pending())
        summary["current_beat"] = self.demo_current_beat
        summary["graph_version"] = self.studio.graph.graph_version
        summary["backend"] = self.cfg.veo_backend
        summary["is_mock_clickhouse"] = self.mirror.is_mock
        return summary

    def get_graph_data(self) -> dict[str, Any]:
        db = self.studio.graph._db
        assets = [dict(r) for r in db.execute("SELECT asset_id, label FROM assets").fetchall()]
        edges = [dict(r) for r in db.execute("SELECT asset_id, ingredient_id FROM edges").fetchall()]
        claims = [dict(r) for r in db.execute("SELECT * FROM claims").fetchall()]

        claims_by_asset: dict[str, list[dict]] = {}
        for c in claims:
            claims_by_asset.setdefault(c["asset_id"], []).append(c)

        nodes = []
        for a in assets:
            aid = a["asset_id"]
            c_list = claims_by_asset.get(aid, [])
            is_composite = any(e["asset_id"] == aid for e in edges)
            has_untrusted = any(not c["trusted"] for c in c_list)
            nodes.append({
                "id": aid,
                "label": a.get("label", aid),
                "is_composite": is_composite,
                "has_untrusted": has_untrusted,
                "claims_count": len(c_list),
                "claims": [{
                    "claim_id": c["claim_id"],
                    "kind": c["kind"],
                    "signer": c["signer"],
                    "trusted": bool(c["trusted"]),
                    "valid_until": c.get("valid_until"),
                } for c in c_list],
            })

        links = [{"source": e["ingredient_id"], "target": e["asset_id"]} for e in edges]
        return {"nodes": nodes, "links": links}

    def preflight_check(self, asset_id: str, verb: str, channel: str | None = None,
                        territory: str | None = None) -> dict[str, Any]:
        verdict = self.studio.check_permission(verb, asset_id, channel=channel, territory=territory)
        # Mirror to ClickHouse
        self.mirror.sync_from_sqlite(self.studio.graph)
        return verdict

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        ledger = CountersignLedger(self.studio.graph)
        return ledger.pending()

    def approve_countersign(self, draft_id: str, approver: str = "Studio Legal Lead") -> dict[str, Any]:
        ledger = CountersignLedger(self.studio.graph)
        pending = ledger.pending()
        matches = [r for r in pending if r["draft_id"] == draft_id]
        if not matches:
            return {"ok": False, "error": f"Draft '{draft_id}' not found in pending queue."}
        row = matches[0]
        draft = DraftInstrument(
            draft_id=row["draft_id"],
            asset_id=row["asset_id"],
            claim_kind=ClaimKind(row["kind"]),
            odrl=json.loads(row["odrl_json"]),
            summary=row["summary"],
            drafted_from_hint="",
        )
        try:
            claim_id = ledger.approve(draft, approver=approver)
            self.mirror.sync_from_sqlite(self.studio.graph)
            return {"ok": True, "claim_id": claim_id, "approver": approver}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


class StudioRequestHandler(http.server.BaseHTTPRequestHandler):
    """REST API & static file handler."""

    engine: StudioEngine

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status":
            self._send_json({"ok": True, "status": "ONLINE", "summary": self.engine.get_summary()})
        elif path == "/api/summary":
            self._send_json({"ok": True, "data": self.engine.get_summary()})
        elif path == "/api/graph":
            self._send_json({"ok": True, "data": self.engine.get_graph_data()})
        elif path == "/api/decisions":
            decisions = self.engine.studio.graph.all_decisions()
            self._send_json({"ok": True, "data": decisions})
        elif path == "/api/countersign/pending":
            pending = self.engine.get_pending_approvals()
            self._send_json({"ok": True, "data": pending})
        elif path == "/api/analytics":
            self.engine.mirror.sync_from_sqlite(self.engine.studio.graph)
            latencies = self.engine.mirror.get_gate_latency_percentiles()
            denies = self.engine.mirror.get_deny_reasons_histogram()
            alerts = self.engine.mirror.get_expiring_window_alerts()
            chains = self.engine.mirror.get_chain_depth_vs_clearance()
            self._send_json({
                "ok": True,
                "data": {
                    "latencies": latencies,
                    "denials": denies,
                    "expiring_alerts": alerts,
                    "chain_depth": chains,
                },
            })
        elif path == "/api/demo/logs":
            self._send_json({"ok": True, "data": self.engine.demo_logs, "current_beat": self.engine.demo_current_beat})
        elif path == "/api/certificate/export":
            from doctus.inspector.generator import generate_inspector_html
            html_cert = generate_inspector_html(self.engine.studio.graph, title="Doctus Verified E&O Certificate")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="doctus_eo_certificate.html"')
            self.end_headers()
            self.wfile.write(html_cert.encode("utf-8"))
        elif path == "/" or path == "/index.html":
            self._serve_static_file("index.html", "text/html; charset=utf-8")
        else:
            # Fallback static files
            safe_file = Path(path.lstrip("/")).name
            file_path = STATIC_DIR / safe_file
            if file_path.exists() and file_path.is_file():
                content_type = "text/plain"
                if safe_file.endswith(".html"):
                    content_type = "text/html; charset=utf-8"
                elif safe_file.endswith(".css"):
                    content_type = "text/css"
                elif safe_file.endswith(".js"):
                    content_type = "application/javascript"
                elif safe_file.endswith(".svg"):
                    content_type = "image/svg+xml"
                self._serve_static_file(safe_file, content_type)
            else:
                self._send_json({"error": f"Path '{path}' not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/preflight":
            asset_id = body.get("asset_id", "")
            verb = body.get("verb", "publish")
            channel = body.get("channel") or None
            territory = body.get("territory") or None
            if not asset_id:
                self._send_json({"ok": False, "error": "asset_id is required"}, status=400)
                return
            verdict = self.engine.preflight_check(asset_id, verb, channel=channel, territory=territory)
            self._send_json({"ok": True, "verdict": verdict})

        elif path == "/api/countersign/approve":
            draft_id = body.get("draft_id", "")
            approver = body.get("approver", "Elena Vance (Studio Legal Lead)")
            if not draft_id:
                self._send_json({"ok": False, "error": "draft_id is required"}, status=400)
                return
            res = self.engine.approve_countersign(draft_id, approver=approver)
            self._send_json(res)

        elif path == "/api/demo/run_beat":
            target_beat = body.get("beat")
            res = self.engine.run_beat(target_beat)
            self._send_json(res)

        elif path == "/api/demo/reset":
            self.engine.reset_demo()
            self._send_json({"ok": True, "message": "Demo state reset."})

        else:
            self._send_json({"error": f"Unknown endpoint {path}"}, status=404)

    def _read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            data = self.rfile.read(length).decode("utf-8")
            return json.loads(data)
        except Exception:
            return {}

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static_file(self, filename: str, content_type: str) -> None:
        target = STATIC_DIR / filename
        if not target.exists():
            self._send_json({"error": f"File '{filename}' not found on server"}, status=404)
            return
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP logs in quiet mode
        pass


class ThreadedStudioServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_studio_server(port: int = 8080, db_path: Path | None = None) -> tuple[ThreadedStudioServer, StudioEngine]:
    engine = StudioEngine(db_path=db_path)
    handler = type("ConfiguredStudioHandler", (StudioRequestHandler,), {"engine": engine})
    server = ThreadedStudioServer(("0.0.0.0", port), handler)
    return server, engine
