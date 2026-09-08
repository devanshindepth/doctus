"""Single-file scan worker: isolated graph, embedded credentials, no shared writes."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

from doctus.engine.compiler import PolicyCompiler
from doctus.engine.gate import ClearanceGate
from doctus.engine.models import ProposedAction, Verb
from doctus.graph.ingest import ManifestIngester
from doctus.graph.store import RightsGraph


def scan_file(path: Path, channel: str, territory: str) -> dict:
    from c2pa import Context, Reader, Settings
    root = Path(__file__).resolve().parents[3]
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    result = {"sha256": digest, "scanned_at": dt.datetime.now(dt.UTC).isoformat(),
              "channel": channel, "territory": territory, "allowed": False,
              "claims": [], "asset_id": None, "credentials_found": False,
              "trust_policy": "Doctus sample trust anchor; third-party signers are not automatically trusted.",
              "retention": "The uploaded file is deleted after scanning. Download this result to keep a copy."}
    graph = RightsGraph(":memory:")
    try:
        settings = Settings.from_dict({
            "verify": {"verify_cert_anchors": True, "verify_trust_list": False,
                       "remote_manifest_fetch": False},
            "trust": {"trust_anchors": (root / "fixtures/pki/demo_root.pem").read_text()},
        })
        try:
            with Context(settings) as context, Reader(str(path), context=context) as reader:
                store = json.loads(reader.json())
        except Exception:
            return {**result, "reason": "NO_VERIFIABLE_CREDENTIALS",
                    "detail": "No readable embedded credentials were found. The file may be unsigned, damaged, or use unsupported credentials.",
                    "next_step": "Ask the creator for the original signed asset and the license covering your intended use. No clearance is confirmed."}
        active = store.get("manifests", {}).get(store.get("active_manifest"))
        if not active:
            return {**result, "reason": "NO_VERIFIABLE_CREDENTIALS", "detail": "No active embedded manifest was found.", "next_step": "Obtain the original signed file and its rights records."}
        result["credentials_found"] = True
        report = ManifestIngester(graph)._ingest_store(path, store)
        result["asset_id"] = report.asset_id
        result["claims"] = [{"claim_id": c.claim_id, "kind": c.kind.value,
                             "signer": c.signer, "trusted": bool(c.trusted)}
                            for c in graph.claims_for([report.asset_id])]
        # No shared graph lookup: an upload cannot borrow an unrelated sample's
        # permissions just by embedding its asset ID or ingredient name.
        if active.get("ingredients"):
            return {**result, "reason": "INGREDIENT_UNCLEARED",
                    "detail": "This file references source ingredients. Their rights cannot be verified from this single-file scan.",
                    "next_step": "Ask your rights team to review the source assets and their licenses before publishing."}
        verdict = ClearanceGate(graph, PolicyCompiler(graph)).check(ProposedAction(
            verb=Verb.PUBLISH, asset_id=report.asset_id, channel=channel, territory=territory))
        return {**result, "allowed": verdict.allowed,
                "reason": verdict.reason.value if verdict.reason else "ALLOWED",
                "detail": verdict.detail or "Recorded permissions cover the requested destination and region under this trust policy.",
                "next_step": "Keep this result with your rights records. It is not legal advice or insurance." if verdict.allowed else
                    (verdict.negotiation_hint or "Ask your rights team to verify the signer and obtain missing permissions.")}
    except Exception:
        return {**result, "reason": "UNREADABLE_CREDENTIALS",
                "detail": "The rights data could not be safely interpreted. No clearance is confirmed.",
                "next_step": "Request an intact original file with supported, signed rights records."}
    finally:
        graph._db.close()


if __name__ == "__main__":
    print(json.dumps(scan_file(Path(sys.argv[1]), sys.argv[2], sys.argv[3])))
