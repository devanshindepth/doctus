"""Demo arc beats 1-5, end-to-end on real signed C2PA media (P3 exit criterion).

Run:  .venv/Scripts/python.exe scripts/demo_arc.py

Wires the P3 agent layer over the prebaked demo media (D9):

  beat 1  ProductionAgent.generate() signs a new Veo-stand-in shot (real C2PA)
          -> ingested trusted with a generation claim
  beat 2  talent frame publishes on its consented channel
  beat 3  ProductionAgent.composite() builds shot + bed -> native ingredient edges
  beat 4  compiled permissions cover the licensed festival publish (ALLOWED)
  beat 5  trailer publish is DENIED: SCOPE_EXCEEDED, named gap, audit row

Everything runtime-generated lands in scratch/p3_demo/ (gitignored); the graph
DB persists there so `scripts/countersign.py --db scratch/p3_demo/doctus.db`
can pick the beat-5 deny up and finish beats 6-8 by hand.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from doctus.agents import Negotiator, ProductionAgent  # noqa: E402
from doctus.agents.countersign import CountersignLedger  # noqa: E402
from doctus.engine.compiler import PolicyCompiler  # noqa: E402
from doctus.engine.gate import ClearanceGate  # noqa: E402
from doctus.engine.models import ClaimKind, Verb  # noqa: E402
from doctus.graph.ingest import ManifestIngester  # noqa: E402
from doctus.graph.store import RightsGraph  # noqa: E402

MEDIA = REPO / "fixtures" / "media"
PKI = REPO / "fixtures" / "pki"
SCRATCH = REPO / "scratch" / "p3_demo"

BEAT = "\n=== beat {} — {} {}"
OK = "  ALLOWED"


def _plain_jpeg(path: Path, caption: str) -> Path:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (320, 180), (10, 60, 120))
    ImageDraw.Draw(img).text((10, 80), caption, fill=(255, 255, 255))
    img.save(path, format="JPEG", quality=90)
    return path


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    db_path = SCRATCH / "doctus.db"
    if db_path.exists():
        db_path.unlink()  # demo runs fresh; the countersign CLI reads it afterwards

    g = RightsGraph(db_path)
    anchor = PKI / "demo_root.pem"
    ingester = ManifestIngester(g, trust_anchors_pem=anchor.read_text(encoding="utf-8"))
    print("ingesting prebaked demo media ...")
    for report in ingester.ingest_directory(MEDIA):
        print(f"  {report.status:11} {report.asset_id}")

    gate = ClearanceGate(g, PolicyCompiler(g))
    agent = ProductionAgent(
        g, gate,
        signer_cert_pem=(PKI / "demo_signer.pem").read_bytes(),
        signer_key_pem=(PKI / "demo_signer.key").read_bytes())

    # ---- beat 1: generate -------------------------------------------------
    print(BEAT.format(1, "generate", "- agent creates a signed Veo stand-in shot"))
    raw = _plain_jpeg(SCRATCH / "_raw_shot.jpg", "VEO SHOT (runtime)")
    out = agent.generate(src_media=str(raw), out_path=str(SCRATCH / "ast_veo_shot_p3.jpg"),
                         asset_id="ast_veo_shot_p3", label="agent-generated hero take")
    print(f"  {out.detail}")
    report = ingester.ingest_file(SCRATCH / "ast_veo_shot_p3.jpg")
    print(f"  ingest: {report.status} trusted={report.trusted} claims={len(report.claim_ids)}")

    # ---- beat 2: consented talent publish ---------------------------------
    print(BEAT.format(2, "publish talent frame", "- likeness consent covers social"))
    v = agent.publish(asset_id="ast_talent_frame_v1", channel="social", territory="US")
    print(OK + f" decision #{v.verdict.decision_id}" if v.ok else f"  DENIED {v.verdict.reason.value}")

    # ---- beat 3: composite --------------------------------------------------
    print(BEAT.format(3, "composite", "- hero + music bed, native ingredient edges"))
    raw_c = _plain_jpeg(SCRATCH / "_raw_composite.jpg", "COMPOSITE (runtime)")
    res = agent.composite(
        src_media=str(raw_c), out_path=str(SCRATCH / "ast_composite_p3.jpg"),
        asset_id="ast_composite_p3", label="hero + bed composite",
        ingredients=[("ast_hero_shot_v1", str(MEDIA / "ast_hero_shot_v1.jpg")),
                     ("ast_music_bed_v1", str(MEDIA / "ast_music_bed_v1.jpg"))])
    print(f"  {res.detail}")
    rep_c = ingester.ingest_file(SCRATCH / "ast_composite_p3.jpg")
    for edge in rep_c.edges:
        print(f"  edge: {edge[0]} <- {edge[1]}")

    # ---- beat 4: compile + allowed publish ---------------------------------
    print(BEAT.format(4, "festival publish", "- chain clears on the licensed channel"))
    v4 = agent.publish(asset_id="ast_composite_p3", channel="festival", territory="US")
    print(OK + f" decision #{v4.verdict.decision_id}" if v4.ok else f"  DENIED {v4.verdict.reason.value}")

    # ---- beat 5: blocked trailer publish ------------------------------------
    print(BEAT.format(5, "trailer publish", "- the gate names the exact gap"))
    v5 = agent.publish(asset_id="ast_composite_p3", channel="trailer", territory="US")
    if v5.ok:
        print("  UNEXPECTED ALLOW - the demo arc expects a block here")
        return 1
    verdict = v5.verdict
    print(f"  DENIED {verdict.reason.value} (decision #{verdict.decision_id})")
    print(f"  detail: {verdict.detail}")
    print(f"  hint:   {verdict.negotiation_hint}")

    # ---- beat 6 (draft only): negotiator proposes the extension -----------
    # NOTE: the extension MUST be the same instrument class as the bed's
    # existing paperwork. The prebaked bed carries an ODRL Offer -> LICENSE;
    # a same-class extension unions within that source, while a different
    # class (e.g. music_clearance) would INTERSECT across sources and
    # collapse the chain (see test_production_pipeline::wrong-instrument).
    print(BEAT.format(6, "negotiate", "- draft instrument registered, NOT signed"))
    draft = Negotiator().draft_extension(
        verdict, asset_id="ast_music_bed_v1", channels=["trailer"],
        territories=["US"], until=dt.datetime(2027, 6, 1, tzinfo=dt.UTC),
        kind=ClaimKind.LICENSE)
    ledger = CountersignLedger(g)
    ledger.propose(draft, proposed_by="negotiator-v1")
    print(f"  {draft.draft_id}")
    print(f"  {draft.summary}")

    total = len(g.all_decisions())
    print(f"\ndecision log: {total} rows at {db_path.relative_to(REPO)}")
    print("next (beats 7-8, by hand):")
    print("  python scripts/countersign.py --db scratch/p3_demo/doctus.db list")
    print("  python scripts/countersign.py --db scratch/p3_demo/doctus.db approve \\")
    print("      urn:doctus:draft:ast_music_bed_v1:license --approver \"Studio Lead\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
