"""GCP wiring configuration, resolved fail-closed (P4, DESIGN.md §6).

Doctus' deterministic core runs locally; the cloud layer adds Veo shot
generation and an Agent Engine deployment on top. Configuration errors refuse
loudly instead of silently falling back to something the operator did not
ask for (CONTEXT.md invariant 2 applied to configuration, not just gates).

Resolution rules:
- ``DOCTUS_VEO_BACKEND`` picks the shot source: ``prebaked`` (default, D9 -
  the committed c2patool-signed fixtures) or ``cloud`` (real Veo via Vertex
  AI; requires billing/quota confirmation, CONTEXT.md Q4).
- ``cloud`` demands GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION; credentials
  themselves surface when the Veo client is constructed (checked there, not
  here, so importing this module never touches network or ADC).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

#: Default Veo checkpoint for the cloud backend (fast tier keeps demo latency
#: sane; override with DOCTUS_VEO_MODEL when a project carries other quotas).
DEFAULT_VEO_MODEL = "veo-3.0-fast-generate-001"

_BACKENDS = ("prebaked", "cloud")


@dataclass(frozen=True)
class CloudConfig:
    """Resolved cloud-layer settings. Immutable; validate via from_env()."""

    veo_backend: str = "prebaked"
    project_id: str | None = None
    location: str | None = None
    veo_model: str = DEFAULT_VEO_MODEL

    @property
    def wants_cloud(self) -> bool:
        return self.veo_backend == "cloud"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CloudConfig":
        """Resolve from environment; unknown backend or cloud-without-project raises."""
        environ = os.environ if env is None else env
        backend = (environ.get("DOCTUS_VEO_BACKEND") or "prebaked").strip().lower()
        if backend not in _BACKENDS:
            raise ValueError(
                f"DOCTUS_VEO_BACKEND='{backend}' is not one of {_BACKENDS}; "
                "refusing to guess (fail-closed)")
        cfg = cls(
            veo_backend=backend,
            project_id=environ.get("GOOGLE_CLOUD_PROJECT") or None,
            location=environ.get("GOOGLE_CLOUD_LOCATION") or None,
            veo_model=environ.get("DOCTUS_VEO_MODEL") or DEFAULT_VEO_MODEL,
        )
        if cfg.wants_cloud:
            cfg.require_cloud()
        return cfg

    def require_cloud(self) -> None:
        """Raise unless the settings name a concrete GCP target."""
        missing = [name for name, val in (
            ("GOOGLE_CLOUD_PROJECT", self.project_id),
            ("GOOGLE_CLOUD_LOCATION", self.location),
        ) if not val]
        if missing:
            raise RuntimeError(
                "DOCTUS_VEO_BACKEND=cloud requires " + ", ".join(missing)
                + ". Set them (gcloud config / .env) or export "
                "DOCTUS_VEO_BACKEND=prebaked for the D9 fallback.")
