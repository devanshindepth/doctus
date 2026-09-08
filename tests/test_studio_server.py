"""Unit and integration tests for Doctus Studio REST Server and Engine."""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

from doctus.server.studio_server import StudioEngine, create_studio_server


def test_studio_engine_direct_apis():
    engine = StudioEngine()
    summary = engine.get_summary()
    assert summary["studio_assets"] >= 1
    assert "clearance_rate" in summary

    # Preflight check on talent frame (social) -> should be allowed
    v_allow = engine.preflight_check("ast_talent_frame_v1", "publish", channel="social", territory="US")
    assert v_allow["allowed"]

    # Preflight check on missing asset -> should be denied with MISSING_MANIFEST
    v_missing = engine.preflight_check("ast_nonexistent", "publish")
    assert not v_missing["allowed"]
    assert v_missing["reason"] == "MISSING_MANIFEST"

    # Preflight check on hero composite for trailer -> denied (SCOPE_EXCEEDED)
    engine.run_beat(3)  # composite hero + music
    v_deny = engine.preflight_check("ast_composite_demo", "publish", channel="trailer", territory="US")
    assert not v_deny["allowed"]
    assert v_deny["reason"] == "SCOPE_EXCEEDED"

    # Run beat 6 (negotiation draft)
    res_b6 = engine.run_beat(6)
    assert res_b6["ok"]
    pending = engine.get_pending_approvals()
    assert len(pending) >= 1

    # Run beat 7 (human countersign approve)
    res_b7 = engine.run_beat(7)
    assert res_b7["ok"]
    assert "claim_id" in res_b7

    # Run beat 8 (re-publish trailer -> ALLOWED)
    res_b8 = engine.run_beat(8)
    assert res_b8["ok"]
    assert res_b8["verdict"]["allowed"]


def test_studio_server_http_endpoints():
    port = 8199
    server, engine = create_studio_server(port=port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.3)

    base = f"http://127.0.0.1:{port}"

    try:
        # 1. GET /api/status
        with urllib.request.urlopen(f"{base}/api/status", timeout=3.0) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"]
            assert data["status"] == "ONLINE"

        # 2. GET /api/summary
        with urllib.request.urlopen(f"{base}/api/summary", timeout=3.0) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"]
            assert "studio_assets" in data["data"]

        # 3. GET /api/graph
        with urllib.request.urlopen(f"{base}/api/graph", timeout=3.0) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"]
            assert "nodes" in data["data"]
            assert "links" in data["data"]

        # 4. POST /api/preflight
        pf_req = urllib.request.Request(
            f"{base}/api/preflight",
            data=json.dumps({"asset_id": "ast_talent_frame_v1", "verb": "publish", "channel": "social"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(pf_req, timeout=3.0) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"]
            assert data["verdict"]["allowed"]

        # 5. GET /api/certificate/export
        with urllib.request.urlopen(f"{base}/api/certificate/export", timeout=3.0) as resp:
            assert resp.status == 200
            html_bytes = resp.read()
            assert b"<!DOCTYPE html>" in html_bytes

        # 6. GET / (static index.html)
        with urllib.request.urlopen(f"{base}/", timeout=3.0) as resp:
            assert resp.status == 200
            html_text = resp.read().decode("utf-8")
            assert "DOCTUS" in html_text
            assert "tailwindcss" in html_text
    finally:
        server.shutdown()
        server.server_close()
