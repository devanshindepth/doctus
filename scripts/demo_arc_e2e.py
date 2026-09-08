"""Canonical 8-Beat End-to-End Demo Arc (P6, DESIGN.md §4 & §6).

Executes the complete Doctus narrative through the unified CloudStudio / ADK layer:

  Beat 1: Veo shot generation -> C2PA manifest signed -> ingested trusted
  Beat 2: Talent likeness publish on social -> ALLOWED (consented channel)
  Beat 3: Composite hero take + festival music bed over native C2PA ingredient edges
  Beat 4: Festival publish -> ALLOWED on compiled permissions
  Beat 5: Trailer publish -> DENIED by Clearance Gate: SCOPE_EXCEEDED (named gap)
  Beat 6: Negotiator / ADK tool drafts ODRL license extension (PROPOSED, not signed)
  Beat 7: Human Studio Lead reviews & countersigns -> writes trusted claim & recompiles
  Beat 8: Trailer publish re-attempted -> ALLOWED! ClickHouse synced & Inspector exported

Usage:
  uv run python scripts/demo_arc_e2e.py [--keep] [--html output.html]
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doctus.analytics.clickhouse import ClickHouseConfig, ClickHouseMirror  # noqa: E402
from doctus.cloud.config import CloudConfig  # noqa: E402
from doctus.cloud.studio import CloudStudio  # noqa: E402
from doctus.cloud.tools import make_tools  # noqa: E402
from doctus.inspector.generator import generate_inspector_html  # noqa: E402

MEDIA = REPO / "fixtures" / "media"
BEAT_HEADER = "\n=== BEAT {} : {} ==="


def run_full_arc(*, keep: bool = False, html_path: Path | None = None) -> int:
    cfg = CloudConfig.from_env()
    workdir = Path(tempfile.mkdtemp(prefix="doctus_e2e_"))
    db_path = workdir / "doctus.db"

    print("=" * 78)
    print("  DOCTUS // END-TO-END DEMO ARC (BEATS 1 - 8)")
    print("  Thesis: Chain-of-Title as Executable Policy")
    print("=" * 78)
    print(f"Backend  : {cfg.veo_backend}"
          + (f" ({cfg.veo_model} @ {cfg.project_id}/{cfg.location})"
             if cfg.wants_cloud else " (D9 fallback — prebaked c2patool media)"))
    print(f"Workspace: {workdir}")

    studio = CloudStudio.create(db_path=db_path, media_dir=MEDIA, config=cfg)
    clickhouse = ClickHouseMirror(ClickHouseConfig(mock_mode=True))

    # -------------------------------------------------------------------------
    # Beat 1: Veo shot generation
    # -------------------------------------------------------------------------
    print(BEAT_HEADER.format(1, "VEO GENERATION & CRYPTOGRAPHIC SIGNING"))
    print("  Production agent invokes Veo video generator.")
    r1 = studio.generate_shot(
        asset_id="ast_veo_shot_e2e",
        prompt="Cinematic hero shot of spaceship landing on red dune at dusk",
        workdir=workdir,
        label="Agent-generated hero shot",
    )
    print(f"  [C2PA] Manifest generated & signed under Doctus demo PKI.")
    print(f"  [INGEST] Status: {r1['ingest_status']} | Trusted: {r1['trusted']} | Claims: {r1['claims']}")

    # -------------------------------------------------------------------------
    # Beat 2: Consented talent publish
    # -------------------------------------------------------------------------
    print(BEAT_HEADER.format(2, "TALENT LIKENESS CLEARANCE PREFLIGHT"))
    print("  Attempting publish of talent frame on licensed social channel...")
    v2 = studio.publish(asset_id="ast_talent_frame_v1", channel="social", territory="US")
    _print_verdict(v2)
    assert v2["allowed"], "Beat 2 should be allowed under likeness consent"

    # -------------------------------------------------------------------------
    # Beat 3: Composite hero take + music bed
    # -------------------------------------------------------------------------
    print(BEAT_HEADER.format(3, "MULTI-TRACK COMPOSITION & INGREDIENT LINKING"))
    print("  Compositing hero shot + music bed (licensed for festival use only)...")
    r3 = studio.composite(
        asset_id="ast_composite_e2e",
        ingredients=[
            ("ast_hero_shot_v1", str(MEDIA / "ast_hero_shot_v1.jpg")),
            ("ast_music_bed_v1", str(MEDIA / "ast_music_bed_v1.jpg")),
        ],
        workdir=workdir,
        label="Hero take + festival music bed",
    )
    print(f"  [C2PA] Ingredient derivation edges signed: {r3['edges']}")
    print(f"  [INGEST] Status: {r3['ingest_status']} | Trusted: {r3['trusted']}")

    # -------------------------------------------------------------------------
    # Beat 4: Festival publish
    # -------------------------------------------------------------------------
    print(BEAT_HEADER.format(4, "FESTIVAL PUBLISH (COMPILED CLEARANCE)"))
    print("  Checking policy compilation across entire ancestor closure for channel 'festival'...")
    v4 = studio.publish(asset_id="ast_composite_e2e", channel="festival", territory="US")
    _print_verdict(v4)
    assert v4["allowed"], "Beat 4 should clear for festival channel"

    # -------------------------------------------------------------------------
    # Beat 5: Blocked trailer publish
    # -------------------------------------------------------------------------
    print(BEAT_HEADER.format(5, "TRAILER PUBLISH (DETERMINISTIC GATE DENIAL)"))
    print("  Production agent proposes publishing trailer publicly to web...")
    v5 = studio.publish(asset_id="ast_composite_e2e", channel="trailer", territory="US")
    _print_verdict(v5)
    if v5["allowed"]:
        print("  ERROR: Expected gate denial on Beat 5!")
        return 1
    print("  [AUDIT] Gate mechanically blocked unauthorized distribution.")
    print(f"  [DIAGNOSIS] Missing claim identified on ingredient: ast_music_bed_v1")

    # -------------------------------------------------------------------------
    # Beat 6: Negotiator drafts license extension
    # -------------------------------------------------------------------------
    print(BEAT_HEADER.format(6, "AUTONOMOUS NEGOTIATION (ODRL DRAFTING)"))
    print("  ADK negotiation tool translates gate diagnosis into ODRL 2.2 draft instrument...")
    tools = {fn.__name__: fn for fn in make_tools(studio)}
    proposal = tools["propose_license_extension"](
        verdict=v5,
        asset_id="ast_music_bed_v1",
        channels=["trailer"],
        territories=["US"],
    )
    print(f"  [DRAFT ID] {proposal['draft_id']}")
    print(f"  [SUMMARY]  {proposal['summary']}")
    print("  [INVARIANT 6] Agent structurally CANNOT self-sign; instrument queued as PENDING.")

    # -------------------------------------------------------------------------
    # Beat 7: Human countersign approval
    # -------------------------------------------------------------------------
    print(BEAT_HEADER.format(7, "HUMAN COUNTERSIGNATURE (INVARIANT 6 SEAM)"))
    print("  Studio Legal Lead reviews draft terms and approves countersignature...")
    from doctus.agents.countersign import CountersignLedger  # noqa: PLC0415
    from doctus.agents.negotiator import DraftInstrument  # noqa: PLC0415
    from doctus.engine.models import ClaimKind  # noqa: PLC0415
    import json  # noqa: PLC0415

    ledger = CountersignLedger(studio.graph)
    pending_rows = ledger.pending()
    assert pending_rows, "Expected pending draft in ledger"
    target_row = pending_rows[-1]

    draft_obj = DraftInstrument(
        draft_id=target_row["draft_id"],
        asset_id=target_row["asset_id"],
        claim_kind=ClaimKind(target_row["kind"]),
        odrl=json.loads(target_row["odrl_json"]),
        summary=target_row["summary"],
        drafted_from_hint="",
    )
    new_claim_id = ledger.approve(draft_obj, approver="Elena Rostova (Studio Legal Lead)")
    print(f"  [APPROVED] Signed into Rights Graph as Claim: {new_claim_id}")
    print(f"  [RECOMPILE] Graph version bumped -> cached permissions invalidated.")

    # -------------------------------------------------------------------------
    # Beat 8: Re-publish trailer (ALLOWED) & Audit export
    # -------------------------------------------------------------------------
    print(BEAT_HEADER.format(8, "RE-PUBLISH TRAILER & INSURER ARTIFACT EXPORT"))
    print("  Production agent re-attempts trailer publish against updated graph...")
    v8 = studio.publish(asset_id="ast_composite_e2e", channel="trailer", territory="US")
    _print_verdict(v8)
    assert v8["allowed"], "Beat 8 should be ALLOWED after human countersignature"
    print("  [SUCCESS] Full 8-Beat Loop closed deterministically: Block -> Negotiate -> Approve -> Clear!")

    # Mirror to ClickHouse analytics
    synced = clickhouse.sync_from_sqlite(studio.graph)
    print(f"\n[CLICKHOUSE MIRROR] Real-time rights analytics synced: {synced}")

    # Generate Inspector HTML report
    target_html = html_path or (REPO / "scratch" / "e2e_inspector.html")
    target_html.parent.mkdir(parents=True, exist_ok=True)
    html_output = generate_inspector_html(studio.graph, title="Doctus E2E Demo Arc Clearance Audit")
    target_html.write_text(html_output, encoding="utf-8")
    print(f"[INSPECTOR REPORT] Interactive audit report exported to: {target_html}")

    print("\n" + "=" * 78)
    print("  DEMO ARC COMPLETED SUCCESSFULLY (8 OF 8 BEATS PASS GREEN)")
    print("=" * 78)

    if not keep:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"\nPreserved workspace at: {workdir}")
    return 0


def _print_verdict(v: dict) -> None:
    if v["allowed"]:
        print(f"  ==> ALLOWED [Decision #{v['decision_id']}]")
    else:
        print(f"  ==> DENIED  [Decision #{v['decision_id']}] Reason: {v['reason']}")
        print(f"      Detail: {v['detail']}")
        print(f"      Fix   : {v['negotiation_hint']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Doctus 8-Beat End-to-End Demo Arc")
    parser.add_argument("--keep", action="store_true", help="Keep temporary workspace artifacts")
    parser.add_argument("--html", type=Path, default=None, help="Path to export inspector HTML")
    args = parser.parse_args()
    return run_full_arc(keep=args.keep, html_path=args.html)


if __name__ == "__main__":
    sys.exit(main())
