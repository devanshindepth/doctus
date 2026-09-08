"""Veo shot backends for beat 1 (P4, DESIGN.md §6): prebaked fallback vs cloud.

Both backends return a local media path the production agent can sign; the
signing + ingest path is IDENTICAL either way, which is the whole point of D9
- swapping the shot source never touches authorization.

The ``cloud`` backend uses Vertex AI Veo through ``google-genai``
(``client.models.generate_videos`` -> poll ``operation`` ->
``video_bytes``/URI). It imports the SDK lazily and raises typed errors when
the SDK or credentials are missing so callers degrade cleanly to ``prebaked``.
"""
from __future__ import annotations

import abc
import time
from pathlib import Path

#: Poll cadence / ceiling for Veo long-running operations (shots take ~30s-2m).
VEO_POLL_SECONDS = 15.0
VEO_TIMEOUT_SECONDS = 600.0


class CloudUnavailableError(RuntimeError):
    """A cloud dependency (SDK or credentials) is missing at call time."""


class ShotBackend(abc.ABC):
    """Source of raw shots for ProductionAgent.generate()."""

    @abc.abstractmethod
    def fetch(self, *, prompt: str, out_path: Path) -> Path:
        """Produce a raw media file at ``out_path``; return its path."""


class PrebakedShotBackend(ShotBackend):
    """D9 fallback: render a placeholder frame from the committed fixtures.

    The demo arc needs *a* real image to wrap in a signed manifest - pixel
    provenance is irrelevant to authorization (the gate reads manifests, not
    pixels), so a rendered frame keeps the loop offline-deterministic.
    """

    def __init__(self, size: tuple[int, int] = (320, 180)) -> None:
        self.size = size

    def fetch(self, *, prompt: str, out_path: Path) -> Path:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:  # pragma: no cover - dev-group dep
            raise RuntimeError(
                "pillow is required for the prebaked shot backend") from exc
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", self.size, (10, 60, 120))
        ImageDraw.Draw(img).text((10, self.size[1] // 2), prompt[:48],
                                 fill=(255, 255, 255))
        img.save(out_path, format="JPEG", quality=90)
        return out_path


class CloudVeoShotBackend(ShotBackend):
    """Real beat 1: text-to-video via Vertex AI Veo (google-genai SDK)."""

    def __init__(self, *, project_id: str, location: str,
                 model: str, poll_seconds: float = VEO_POLL_SECONDS,
                 timeout_seconds: float = VEO_TIMEOUT_SECONDS) -> None:
        if not project_id or not location:
            raise ValueError("CloudVeoShotBackend needs project_id and location")
        self.project_id = project_id
        self.location = location
        self.model = model
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------ API
    def fetch(self, *, prompt: str, out_path: Path) -> Path:
        client = self._client()
        op = client.models.generate_videos(
            model=self.model,
            prompt=prompt,
            config={"aspect_ratio": "16:9", "number_of_videos": 1},
        )
        deadline = time.monotonic() + self.timeout_seconds
        while not op.done:
            if time.monotonic() > deadline:
                raise TimeoutError(f"veo operation did not finish in "
                                   f"{self.timeout_seconds:.0f}s: {prompt[:60]}")
            time.sleep(self.poll_seconds)
            op = client.operations.get(op)
        videos = getattr(getattr(op, "response", None), "generated_videos", None) or []
        if not videos or getattr(videos[0], "video", None) is None:
            raise RuntimeError("veo returned an operation with no video payload")
        video = videos[0].video
        data = getattr(video, "video_bytes", None)
        if data is None and getattr(video, "uri", None):
            import urllib.request  # noqa: PLC0415 - stdlib suffices for GCS GET

            data = urllib.request.urlopen(video.uri, timeout=120).read()
        if not data:
            raise RuntimeError("veo video carried neither bytes nor a readable URI")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return out_path

    # ------------------------------------------------------------ internals
    def _client(self):
        """Construct the genai client here so ADC problems surface as one error."""
        try:
            from google import genai
        except ImportError as exc:
            raise CloudUnavailableError(
                "google-genai is not installed - add the 'gcp' dependency group "
                "(uv sync --group gcp) or export DOCTUS_VEO_BACKEND=prebaked") from exc
        try:
            return genai.Client(vertexai=True,
                                project=self.project_id, location=self.location)
        except Exception as exc:  # noqa: BLE001 - any ADC failure fails closed
            raise CloudUnavailableError(
                f"could not build a Vertex AI client for {self.project_id}/"
                f"{self.location}: {exc}. Run `gcloud auth application-default "
                "login` or fall back to DOCTUS_VEO_BACKEND=prebaked") from exc


def shot_backend_from_config(cfg) -> ShotBackend:
    """Factory: CloudConfig -> backend instance. Unknown backends raise."""
    name = getattr(cfg, "veo_backend", "prebaked")
    if name == "prebaked":
        return PrebakedShotBackend()
    if name == "cloud":
        cfg.require_cloud()
        return CloudVeoShotBackend(project_id=cfg.project_id,
                                   location=cfg.location, model=cfg.veo_model)
    raise ValueError(f"unknown veo backend '{name}' (fail-closed)")
