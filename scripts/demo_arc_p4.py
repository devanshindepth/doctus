"""P4 exit criterion, offline leg (DESIGN.md §6): the wired demo arc.

Run:  .venv/Scripts/python.exe scripts/demo_arc_p4.py

Same beats as scripts/demo_arc.py (P3) but driven through the CloudStudio /
ADK tool layer that Agent Engine will host:

  beat 1  Veo shot via the configured backend (DOCTUS_VEO_BACKEND,
          default prebaked per D9) -> signed -> ingested trusted
  beat 2  talent publish on its consented channel
  beat 3  composite shot + bed over native ingredient edges
  beat 4  festival publish clears on compiled permissions
  beat 5  trailer publish DENIED: SCOPE_EXCEEDED + named gap
  beat 6  ADK tool layer drafts the same-class extension (proposed only)
  beat 7-8 human countersign (scripts/countersign.py) closes the arc
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doctus.cloud.config import CloudConfig  # noqa: E402
from doctus.cloud.studio import CloudStudio  # noqa: E402

MEDIA = REPO / "fixtures" / "media"
BEAT = "\n=== beat {} — {} {}"
OK = "  ALLOWED"


def main() -> int:
    cfg = CloudConfig.from_env()
    workdir = Path(tempfile.mkdtemp(prefix="doctus_p4_"))
    db_path = workdir / "doctus.db"
    print(f"veo backend : {cfg.veo_backend}"
          + (f" ({cfg.veo_model} @ {cfg.project_id}/{cfg.location})"
             if cfg.wants_cloud else " (D9 fallback - committed fixtures)"))
    print(f"workspace   : {workdir}")

    studio = CloudStudio.create(db_path=db_path, media_dir=MEDIA, config=cfg)

    # ---- beat 1: generate --------------------------------------------------
    print(BEAT.format(1, "generate", f"- shot source: {type(studio.backend).__name__}"))
    r1 = studio.generate_shot(asset_id="ast_veo_shot_p4",
                              prompt="VEO SHOT (p4 wired loop)",
                              workdir=workdir, label="agent-generated hero take")
    _print_ingest(r1)

    # ---- beat 2: consented talent publish -----------------------------------
    print(BEAT.format(2, "publish talent frame", "- likeness consent covers social"))
    v = studio.publish(asset_id="ast_talent_frame_v1", channel="social", territory="US")
    _print_verdict(v)

    # ---- beat 3: composite --------------------------------------------------
    print(BEAT.format(3, "composite", "- hero + music bed, native ingredient edges"))
    r3 = studio.composite(
        asset_id="ast_composite_p4",
        ingredients=[("ast_hero_shot_v1", str(MEDIA / "ast_hero_shot_v1.jpg")),
                     ("ast_music_bed_v1", str(MEDIA / "ast_music_bed_v1.jpg"))],
        workdir=workdir, label="hero + bed composite")
    _print_ingest(r3)

    # ---- beat 4: allowed publish -------------------------------------------
    print(BEAT.format(4, "festival publish", "- chain clears on the licensed channel"))
    v4 = studio.publish(asset_id="ast_composite_p4", channel="festival", territory="US")
    _print_verdict(v4)

    # ---- beat 5: blocked trailer publish ------------------------------------
    print(BEAT.format(5, "trailer publish", "- the gate names the exact gap"))
    v5 = studio.publish(asset_id="ast_composite_p4", channel="trailer", territory="US")
    _print_verdict(v5)
    if v5["allowed"]:
        print("  UNEXPECTED ALLOW - the demo arc expects a block here")
        return 1

    # ---- beat 6: draft via the ADK tool layer -------------------------------
    print(BEAT.format(6, "negotiate", "- ADK tool drafts extension, NOT signed"))
    from doctus.cloud.tools import make_tools  # noqa: PLC0415

    tools = {fn.__name__: fn for fn in make_tools(studio)}
    proposal = tools["propose_license_extension"](
        verdict=v5, asset_id="ast_music_bed_v1",
        channels=["trailer"], territories=["US"])
    print(f"  {proposal['draft_id']}")
    print(f"  {proposal['summary']}")

    total = len(studio.graph.all_decisions())
    print(f"\ndecision log: {total} rows at {db_path}")
    print("next (beats 7-8, by hand):")
    print(f"  python scripts/countersign.py --db {db_path} list")
    print("  python scripts/countersign.py --db <db> approve \\")
    print('      urn:doctus:draft:ast_music_bed_v1:license --approver "Studio Lead"')

    if "--keep" not in sys.argv:
        shutil.rmtree(workdir, ignore_errors=True)
        print("\n(workspace cleaned; rerun with --keep to inspect artifacts)")
    return 0


def _print_ingest(r: dict) -> None:
    status = f"{r['ingest_status']} trusted={r['trusted']}" if r.get("ok") else "REFUSED"
    print(f"  ingest: {status} claims={r.get('claims', 0)} "
          f"edges={r.get('edges', []) or '-'}")
    if not r["ok"]:
        print(f"  detail: {r['detail']}")


def _print_verdict(v: dict) -> None:
    if v["allowed"]:
        print(OK + f" decision #{v['decision_id']}")
    else:
        print(f"  DENIED {v['reason']} (decision #{v['decision_id']})")
        print(f"  detail: {v['detail']}")
        print(f"  hint:   {v['negotiation_hint']}")


if __name__ == "__main__":
    sys.exit(main())
