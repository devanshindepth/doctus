"""Doctus production agent for Vertex AI Agent Engine (P4, DESIGN.md §3.4).

ADK's loader imports this module and picks up ``root_agent`` (or an ``agent``
object). The agent plane is a Gemini planner; every tool call below it is
deterministic Doctus code - generate/composite sign real C2PA manifests,
publish routes through the ClearanceGate, and deny verdicts come back as data
the model must read (it cannot prompt-fuzz the gate; CONTEXT.md §1/D3).

Cloud settings arrive via environment (CloudConfig.from_env):
  DOCTUS_VEO_BACKEND   prebaked (default, D9) | cloud
  GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION   required for backend=cloud
"""
from __future__ import annotations

import sys
from pathlib import Path

# Deployment layout: deploy/adk_app/agent.py -> repo root is three up.
_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from doctus.cloud.config import CloudConfig  # noqa: E402
from doctus.cloud.studio import CloudStudio  # noqa: E402

#: One CloudStudio per agent instance. DB lives on the deployment filesystem;
#: P5's ClickHouse mirror is where cross-instance durability lands.
STUDIO = CloudStudio.create(db_path="doctus_agent_engine.db", config=CloudConfig.from_env())

try:  # pragma: no cover - exercised only where google-adk is installed
    from doctus.cloud.tools import build_agent  # noqa: PLC0415 - lazy SDK import

    root_agent = build_agent(STUDIO)
except Exception as _exc:  # noqa: BLE001 - surface a precise load error
    raise RuntimeError(
        f"failed to assemble the Doctus ADK agent: {_exc}. "
        "Agent Engine needs the 'adk' dependency group (see deploy/README.md); "
        "locally you can still run scripts/demo_arc_p4.py.") from _exc
