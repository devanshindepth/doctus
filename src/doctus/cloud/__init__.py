"""P4 cloud wiring: GCP config, Veo shot backends, CloudStudio, ADK tool layer.

Layout mirrors the repo convention (engine/, graph/, agents/): the cloud
package is glue - it assembles existing deterministic components and adds the
real-cloud seams (Veo generation, Agent Engine deployment). The authorization
core never depends on it (DESIGN.md §3.5: partner/cloud layers enrich; the
engine stands alone).
"""
from doctus.cloud.config import CloudConfig
from doctus.cloud.studio import CloudStudio

__all__ = ["CloudConfig", "CloudStudio"]
