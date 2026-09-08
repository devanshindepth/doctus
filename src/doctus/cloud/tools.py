"""ADK tool surface for the Doctus production agent (P4, DESIGN.md §3.4/§6).

The agent plane is a Gemini LLM inside Google ADK; these functions are the
ONLY actions it can take. Every side-effectful tool routes through the
ClearanceGate first and returns deny explanations verbatim - the model sees
the named gap and the negotiation path, but cannot prompt-fuzz a deterministic
gate (CONTEXT.md §1). The gate decides; the model proposes.

``build_agent()`` degrades gracefully: without google-adk installed it raises
a typed error telling the operator which group to install; the deploy scaffold
pins that group (see deploy/README.md). Tool docstrings are written for the
model - ADK renders them into the function-calling schema.
"""
from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path
from typing import Any

from doctus.cloud.studio import CloudStudio


class AdkNotInstalledError(RuntimeError):
    """google-adk missing - install it (uv sync --group adk) to run the agent."""


def _require_adk():
    try:
        import google.adk  # noqa: F401,PLC0415 - presence check for the builder
    except ImportError as exc:
        raise AdkNotInstalledError(
            "google-adk is not installed in this environment - "
            "`uv sync --group adk` (see deploy/README.md)") from exc


def make_tools(studio: CloudStudio) -> list:
    """Bind the studio's deterministic tools for an ADK LlmAgent.

    Returned callables close over ONE CloudStudio instance: they are plain
    Python functions with docstrings, exactly what ``LlmAgent(tools=...)``
    wraps as function tools.
    """

    def generate_shot(asset_id: str, prompt: str) -> dict[str, Any]:
        """Create a new AI-generated shot and register its signed provenance.

        Args:
            asset_id: Unique asset id for the new shot, e.g. ast_shot_01.
            prompt: What the shot should show.

        Returns:
            Dict with ok, asset_id, ingest_status, trusted, claims.
        """
        return studio.generate_shot(
            asset_id=asset_id, prompt=prompt,
            workdir=Path(tempfile.gettempdir()) / "doctus_shots")

    def composite_shot(asset_id: str, ingredient_asset_ids: list[str]) -> dict[str, Any]:
        """Composite existing assets into a new asset with provenance edges.

        Args:
            asset_id: Unique asset id for the new composite.
            ingredient_asset_ids: Asset ids to combine, e.g. hero + music bed.

        Returns:
            Dict with ok, asset_id, edges (ingredient links), trusted.
        """
        ingredients = [(aid, _resolve_media(studio, aid))
                       for aid in ingredient_asset_ids]
        return studio.composite(asset_id=asset_id, ingredients=ingredients,
                                workdir=Path(tempfile.gettempdir()) / "doctus_shots",
                                label=" + ".join(ingredient_asset_ids))

    def publish_video(asset_id: str, channel: str, territory: str) -> dict[str, Any]:
        """Attempt to publish an asset on a channel; the clearance gate decides.

        Args:
            asset_id: Asset to publish.
            channel: Distribution channel, e.g. festival, social, trailer.
            territory: Two-letter market, e.g. US.

        Returns:
            Verdict dict: allowed, reason, detail, negotiation_hint.
            A DENY is a normal result - read reason/detail and either draft an
            extension via propose_license_extension or pick another channel.
        """
        return studio.publish(asset_id=asset_id, channel=channel, territory=territory)

    def check_permission(verb: str, asset_id: str, channel: str = "",
                         territory: str = "") -> dict[str, Any]:
        """Preflight a permission without side effects.

        Args:
            verb: One of publish, remix, train_on, license_out.
            asset_id: Asset to check.
            channel: Optional channel constraint.
            territory: Optional territory constraint.

        Returns:
            Verdict dict (same shape as publish_video).
        """
        return studio.check_permission(
            verb, asset_id,
            channel=channel or None, territory=territory or None)

    def propose_license_extension(verdict: dict, asset_id: str,
                                  channels: list[str], territories: list[str]) -> dict:
        """Turn a DENY verdict into a draft license extension for human approval.

        Args:
            verdict: The deny verdict dict returned by publish_video.
            asset_id: The asset whose chain has the gap (e.g. the music bed).
            channels: Channels the extension should grant.
            territories: Territories the extension should grant.

        Returns:
            Draft summary for the human countersign queue. NEVER approves -
            only a human approval turns a draft into rights.
        """
        draft = studio.draft_extension(
            verdict, asset_id=asset_id, channels=list(channels),
            territories=list(territories),
            until=dt.datetime.now(dt.UTC) + dt.timedelta(days=365),
            kind="license")
        studio.propose_draft(draft)
        return {"draft_id": draft.draft_id, "summary": draft.summary}

    return [generate_shot, composite_shot, publish_video, check_permission,
            propose_license_extension]


def build_agent(studio: CloudStudio, *, model: str = "gemini-2.5-flash"):
    """Assemble the ADK LlmAgent over the bound tools (requires google-adk)."""
    _require_adk()
    from google.adk.agents import LlmAgent  # noqa: PLC0415

    return LlmAgent(
        name="doctus_producer",
        model=model,
        description=("AI film producer whose every side effect is authorized by "
                     "signed provenance credentials through a deterministic "
                     "clearance gate."),
        instruction=(
            "You plan and produce a short film from generated shots.\n"
            "Rules you must never break:\n"
            "1. Create assets ONLY via generate_shot / composite_shot.\n"
            "2. Before any publish, you may check_permission; publishing itself "
            "MUST go through publish_video - its verdict is final.\n"
            "3. On DENY: read 'reason' and 'detail'. Never retry the same call "
            "hoping for a different answer. Either publish on a covered channel "
            "or use propose_license_extension to draft the cure for a human to "
            "approve. You can never approve anything yourself.\n"
            "4. Report every verdict (allow or deny) with its decision id."),
        tools=make_tools(studio),
    )


def _resolve_media(studio: CloudStudio, asset_id: str) -> str:
    """Locate the signed media file backing an ingested asset."""
    candidate = Path(tempfile.gettempdir()) / "doctus_shots" / f"{asset_id}.jpg"
    if candidate.exists():
        return str(candidate)
    media_dir = Path(__file__).resolve().parents[3] / "fixtures" / "media"
    prebaked = media_dir / f"{asset_id}.jpg"
    if prebaked.exists():
        return str(prebaked)
    raise FileNotFoundError(
        f"no media found for '{asset_id}' - generate it first")
