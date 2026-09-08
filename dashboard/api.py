"""
Doctus Clearance Studio — Production FastAPI Backend.

Provides deterministic rights clearance verification, C2PA provenance graph querying,
ODRL 2.2 countersignature workflow, ClickHouse analytics telemetry, and demo arc orchestration.
Also serves the React SPA frontend and media fixtures.

Usage:
    uvicorn dashboard.api:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Ensure repo / src is importable
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from doctus.inspector.generator import generate_inspector_html
from doctus.server.studio_server import StudioEngine
from dashboard.uploads import router as uploads_router

# ─────────────────────────────────────────────────────────── Global Engine State
_engine: StudioEngine | None = None
_FRONTEND_DIST = _REPO / "frontend" / "dist"
_MEDIA_DIR = _REPO / "fixtures" / "media"
_LEGACY_HTML = _REPO / "dashboard" / "dashboard.html"


def get_engine() -> StudioEngine:
    global _engine
    if _engine is None:
        _engine = StudioEngine()
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize engine and verify initial seed
    engine = get_engine()
    yield
    # Shutdown logic


app = FastAPI(
    title="Doctus Clearance Studio API",
    description="Deterministic AI rights clearance engine & provenance studio",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(uploads_router)

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────── Pydantic Request Models
class PreflightRequest(BaseModel):
    asset_id: str = Field(..., description="Target asset identifier")
    verb: str = Field("publish", description="Proposed action verb: publish, remix, train_on, license_out")
    channel: str | None = Field(None, description="Distribution channel e.g. social, festival, trailer")
    territory: str | None = Field("US", description="Territory code e.g. US, EU, Global")


class CountersignApproveRequest(BaseModel):
    draft_id: str = Field(..., description="Unique draft instrument ID to approve")
    approver: str = Field("Elena Vance (Studio Legal Lead)", description="Human authority signing the instrument")


class DemoRunBeatRequest(BaseModel):
    beat: int | None = Field(None, description="Target beat number (1-8), or null for next beat")


# ─────────────────────────────────────────────────────────── REST Endpoints


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for Cloud Run and load balancers."""
    engine = get_engine()
    return {
        "status": "healthy",
        "service": "doctus-clearance-studio",
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "graph_version": engine.studio.graph.graph_version,
    }


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Returns studio operational status and executive summary."""
    engine = get_engine()
    return {
        "ok": True,
        "status": "ONLINE",
        "summary": engine.get_summary(),
    }


@app.get("/api/summary")
async def get_summary() -> dict[str, Any]:
    """Returns executive clearance KPIs and countersign status."""
    engine = get_engine()
    return {"ok": True, "data": engine.get_summary()}


@app.get("/api/graph")
async def get_graph() -> dict[str, Any]:
    """Returns nodes and links for C2PA provenance DAG visualization."""
    engine = get_engine()
    return {"ok": True, "data": engine.get_graph_data()}


@app.get("/api/decisions")
async def get_decisions() -> dict[str, Any]:
    """Returns complete audit trail of gate clearance decisions."""
    engine = get_engine()
    decisions = engine.studio.graph.all_decisions()
    return {"ok": True, "data": decisions}


@app.get("/api/countersign/pending")
async def get_countersign_pending() -> dict[str, Any]:
    """Returns pending ODRL license instruments awaiting human countersignature."""
    engine = get_engine()
    return {"ok": True, "data": engine.get_pending_approvals()}


@app.get("/api/analytics")
async def get_analytics() -> dict[str, Any]:
    """Returns ClickHouse telemetry: latency percentiles, denial histogram, and expiring alerts."""
    engine = get_engine()
    engine.mirror.sync_from_sqlite(engine.studio.graph)
    latencies = engine.mirror.get_gate_latency_percentiles()
    denials = engine.mirror.get_deny_reasons_histogram()
    alerts = engine.mirror.get_expiring_window_alerts()
    chains = engine.mirror.get_chain_depth_vs_clearance()
    return {
        "ok": True,
        "data": {
            "latencies": latencies,
            "denials": denials,
            "expiring_alerts": alerts,
            "chain_depth": chains,
        },
    }


@app.get("/api/demo/logs")
async def get_demo_logs() -> dict[str, Any]:
    """Returns the history of demo events executed in the current session."""
    engine = get_engine()
    return {
        "ok": True,
        "data": engine.demo_logs,
        "current_beat": engine.demo_current_beat,
    }


@app.get("/api/certificate/export")
async def export_certificate() -> Response:
    """Exports a self-contained verified E&O Insurance Certificate HTML artifact."""
    engine = get_engine()
    html_content = generate_inspector_html(
        engine.studio.graph,
        title="Doctus Verified E&O Rights Certificate",
    )
    return Response(
        content=html_content,
        media_type="text/html",
        headers={
            "Content-Disposition": 'attachment; filename="doctus_eo_certificate.html"',
        },
    )


@app.post("/api/preflight")
async def run_preflight(req: PreflightRequest) -> dict[str, Any]:
    """Simulate gate clearance for a proposed action on an asset."""
    engine = get_engine()
    verdict = engine.preflight_check(
        asset_id=req.asset_id,
        verb=req.verb,
        channel=req.channel,
        territory=req.territory,
    )
    return {"ok": True, "verdict": verdict}


@app.post("/api/countersign/approve")
async def approve_countersign(req: CountersignApproveRequest) -> dict[str, Any]:
    """Human approval seam: approve and bind an ODRL license instrument into the rights graph."""
    engine = get_engine()
    result = engine.approve_countersign(draft_id=req.draft_id, approver=req.approver)
    if not result.get("ok", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Approval failed"))
    return result


@app.post("/api/demo/run_beat")
async def run_demo_beat(req: DemoRunBeatRequest) -> dict[str, Any]:
    """Execute a step in the 8-beat demo arc."""
    engine = get_engine()
    return engine.run_beat(req.beat)


@app.post("/api/demo/reset")
async def reset_demo() -> dict[str, Any]:
    """Reset the studio and demo state back to clean baseline."""
    engine = get_engine()
    engine.reset_demo()
    return {"ok": True, "message": "Studio state reset to clean baseline."}


# ─────────────────────────────────────────────────────────── Backward-Compatibility Aliases
@app.get("/api/overview")
async def get_overview() -> dict[str, Any]:
    """Legacy overview endpoint alias."""
    return await get_summary()


@app.post("/api/gate/check")
async def gate_check(req: PreflightRequest) -> dict[str, Any]:
    """Legacy gate check endpoint alias."""
    return await run_preflight(req)


@app.get("/api/analytics/summary")
async def get_analytics_summary() -> dict[str, Any]:
    """Legacy analytics summary endpoint alias."""
    return await get_analytics()


@app.get("/api/analytics/graph")
async def get_analytics_graph() -> dict[str, Any]:
    """Legacy analytics graph endpoint alias."""
    return await get_graph()


# ─────────────────────────────────────────────────────────── Static & Media Serving
# Mount fixtures media folder for local streaming
if _MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(_MEDIA_DIR)), name="media")

# Mount React static assets if built
if (_FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")


# SPA Catch-all Route: serve index.html for any frontend client-side route
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(request: Request, full_path: str):
    # If request is for an API route that didn't match, return 404 JSON
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail=f"API route not found: /{full_path}")

    # Check if a specific static file was requested in dist
    if _FRONTEND_DIST.exists():
        potential_file = _FRONTEND_DIST / full_path
        if full_path and potential_file.is_file():
            return FileResponse(potential_file)

        # Otherwise serve the SPA index.html
        index_file = _FRONTEND_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)

    # Fallback to legacy dashboard.html if frontend is not built yet
    if _LEGACY_HTML.exists():
        return HTMLResponse(content=_LEGACY_HTML.read_text(encoding="utf-8"))

    return HTMLResponse(
        content="<h1>Doctus Studio</h1><p>Frontend is building. Please refresh in a moment.</p>",
        status_code=200,
    )
