"""P4 cloud-wiring tests (DESIGN.md §6): seams exist, fail closed, stay offline.

The offline core (engine/graph/agents) never imports google SDKs; these tests
pin the P4 contract:

- config: backend resolution is explicit; 'cloud' without a project refuses.
- veo backends: prebaked renders deterministically; the cloud backend builds
  only with concrete settings and raises typed errors without the SDK/ADC.
- CloudStudio + tool layer: beats 1-5 run end-to-end through the same tool
  surface ADK wraps, on real signed C2PA media (D9 fallback leg of the exit
  criterion); deny-as-data and invariant-6 hold through the wrapper layer.
"""
from __future__ import annotations

import pytest

from doctus.cloud.config import CloudConfig
from doctus.cloud.studio import CloudStudio
from doctus.cloud.tools import AdkNotInstalledError, make_tools
from doctus.cloud.veo import (CloudUnavailableError, CloudVeoShotBackend,
                              PrebakedShotBackend)

REPO = None  # set lazily; CloudStudio.create resolves the repo itself


# ------------------------------------------------------------------ config
def test_default_backend_is_prebaked_without_any_env():
    cfg = CloudConfig.from_env({})
    assert cfg.veo_backend == "prebaked" and not cfg.wants_cloud


def test_unknown_backend_refuses_to_guess():
    with pytest.raises(ValueError, match="DOCTUS_VEO_BACKEND"):
        CloudConfig.from_env({"DOCTUS_VEO_BACKEND": "veo-please"})


def test_cloud_backend_without_project_fails_closed():
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        CloudConfig.from_env({"DOCTUS_VEO_BACKEND": "cloud"})


def test_cloud_backend_with_project_resolves():
    cfg = CloudConfig.from_env({"DOCTUS_VEO_BACKEND": "cloud",
                                "GOOGLE_CLOUD_PROJECT": "doctus-demo",
                                "GOOGLE_CLOUD_LOCATION": "us-central1"})
    assert cfg.wants_cloud and cfg.project_id == "doctus-demo"


# ------------------------------------------------------------------ backends
def test_prebacked_backend_renders_deterministic_frame(tmp_path):
    out = PrebakedShotBackend().fetch(prompt="hero take", out_path=tmp_path / "s.jpg")
    assert out.exists() and out.stat().st_size > 0


def test_cloud_backend_requires_concrete_settings():
    with pytest.raises(ValueError, match="project_id"):
        CloudVeoShotBackend(project_id="", location="", model="m")


def test_cloud_backend_client_missing_sdk_raises_typed_error(monkeypatch):
    """No google-genai installed => CloudUnavailableError, not ImportError."""
    backend = CloudVeoShotBackend(project_id="p", location="l", model="m")
    import builtins
    real_import = builtins.__import__

    def no_genai(name, *a, **k):
        if name.startswith("google"):
            raise ImportError("simulated missing SDK")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_genai)
    with pytest.raises(CloudUnavailableError, match="google-genai"):
        backend.fetch(prompt="x", out_path=None)  # type: ignore[arg-type]


# ------------------------------------------------------- studio + tool layer
@pytest.fixture(scope="module")
def studio(tmp_path_factory):
    from pathlib import Path

    media = Path(__file__).resolve().parent.parent / "fixtures" / "media"
    if not media.exists():
        pytest.skip("prebaked fixtures missing - run scripts/prebake_fixtures.py")
    return CloudStudio.create(
        db_path=":memory:", media_dir=media,
        config=CloudConfig(veo_backend="prebaked"),
        pki_dir=Path(__file__).resolve().parent.parent / "fixtures" / "pki")


def _tools(studio):
    return {fn.__name__: fn for fn in make_tools(studio)}


def test_beat_1_generate_shot_through_tool_layer(studio, tmp_path):
    st = studio
    workdir = tmp_path
    r = st.generate_shot(asset_id="ast_p4_shot_a", prompt="wired hero shot",
                         workdir=workdir)
    assert r["ok"] and r["trusted"], r
    assert r["ingest_status"] == "INGESTED" and r["claims"] >= 1


def test_beats_publish_allow_then_deny_as_data(studio):
    v = studio.publish(asset_id="ast_talent_frame_v1", channel="social", territory="US")
    assert v["allowed"] and v["decision_id"] is not None
    v2 = studio.publish(asset_id="ast_talent_frame_v1", channel="trailer", territory="US")
    assert not v2["allowed"]
    assert v2["reason"] == "SCOPE_EXCEEDED"
    assert "'trailer' outside ['social']" in v2["detail"]  # consent covers social only


def test_tool_surface_composite_and_gate(studio, tmp_path):
    tools = _tools(studio)
    r = tools["composite_shot"]("ast_p4_comp_a", ["ast_hero_shot_v1", "ast_music_bed_v1"])
    assert r["ok"] and {"ast_p4_comp_a", "ast_hero_shot_v1",
                        "ast_music_bed_v1"} <= set(r.get("edges", []) and
                                                   [e for pair in r["edges"] for e in pair])
    v = tools["publish_video"]("ast_p4_comp_a", "festival", "US")
    assert v["allowed"]
    v2 = tools["publish_video"]("ast_p4_comp_a", "trailer", "US")
    assert not v2["allowed"] and v2["reason"] == "SCOPE_EXCEEDED"


def test_negotiation_tool_never_self_signs(studio):
    tools = _tools(studio)
    verdict = tools["publish_video"]("ast_composite_x", "trailer", "US")
    # composite_x does not exist yet -> deny carries no kind; tool pins kind=license
    proposal = tools["propose_license_extension"](verdict, "ast_music_bed_v1",
                                                  ["trailer"], ["US"])
    assert proposal["draft_id"].startswith("urn:doctus:draft:")
    pending = {d["draft_id"] for d in studio.pending_drafts()}
    assert proposal["draft_id"] in pending          # proposed...
    kinds = {c.kind.value for c in studio.graph.claims_for(["ast_music_bed_v1"])
             if c.claim_id.startswith("cs-")}
    assert not kinds                                 # ...but nothing countersigned


def test_human_countersign_closes_the_loop(studio):
    tools = _tools(studio)
    verdict = studio.publish(asset_id="ast_composite_x", channel="trailer", territory="US")
    draft = studio.draft_extension(verdict, asset_id="ast_music_bed_v1",
                                   channels=["trailer"], territories=["US"],
                                   kind="license")
    claim_id = studio.countersign_approve(draft, approver="human-studio-lead")
    assert claim_id.startswith("cs-")
    # union within the bed's source reopens trailer on the bed itself;
    # full-chain effects are pinned by test_production_pipeline.py.


def test_build_agent_without_adk_raises_typed_error(studio):
    from doctus.cloud.tools import build_agent

    with pytest.raises(AdkNotInstalledError):
        build_agent(studio)
