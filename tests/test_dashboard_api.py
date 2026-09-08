"""Integration tests for Doctus Dashboard FastAPI server."""
from __future__ import annotations

import json
import threading
import time
import urllib.request
import uvicorn
import pytest

from dashboard.api import app, get_engine


@pytest.fixture(scope="module")
def api_server():
    port = 8399
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.8)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


def test_api_health(api_server):
    with urllib.request.urlopen(f"{api_server}/api/health", timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "healthy"
        assert "graph_version" in data


def test_api_summary_and_status(api_server):
    with urllib.request.urlopen(f"{api_server}/api/summary", timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"]
        assert data["data"]["studio_assets"] >= 1
        assert "clearance_rate" in data["data"]

    with urllib.request.urlopen(f"{api_server}/api/status", timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"]
        assert data["status"] == "ONLINE"


def test_api_graph(api_server):
    with urllib.request.urlopen(f"{api_server}/api/graph", timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"]
        nodes = data["data"]["nodes"]
        assert len(nodes) >= 1
        assert any(n["id"] == "ast_talent_frame_v1" for n in nodes)


def test_api_preflight_and_negotiate(api_server):
    # 1. Allowed preflight
    req_allow = urllib.request.Request(
        f"{api_server}/api/preflight",
        data=json.dumps({
            "asset_id": "ast_talent_frame_v1",
            "verb": "publish",
            "channel": "social",
            "territory": "US",
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_allow, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"]
        assert data["verdict"]["allowed"] is True

    # 2. Denied preflight (missing asset)
    req_deny = urllib.request.Request(
        f"{api_server}/api/preflight",
        data=json.dumps({
            "asset_id": "ast_unknown_asset",
            "verb": "publish",
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_deny, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"]
        assert data["verdict"]["allowed"] is False
        assert data["verdict"]["reason"] == "MISSING_MANIFEST"


def test_api_demo_lifecycle(api_server):
    # Reset demo
    req_reset = urllib.request.Request(
        f"{api_server}/api/demo/reset",
        data=json.dumps({}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_reset, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"]

    # Run beat 1
    req_b1 = urllib.request.Request(
        f"{api_server}/api/demo/run_beat",
        data=json.dumps({"beat": 1}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_b1, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"]
        assert data["beat"] == 1


def test_api_spa_and_media_serving(api_server):
    # Static SPA HTML
    with urllib.request.urlopen(f"{api_server}/", timeout=3.0) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "Doctus" in content
        assert "root" in content

    # Media streaming
    with urllib.request.urlopen(f"{api_server}/media/ast_video_shot_v1.mp4", timeout=3.0) as resp:
        assert resp.status == 200
        assert len(resp.read()) > 1000
