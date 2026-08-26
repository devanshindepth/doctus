"""Sign new media with Doctus C2PA manifests at production time.

The P1 prebake script signs fixtures offline; this module is its runtime
sibling for the production agent (DESIGN.md §3.4): every generative /
compositing tool wraps its output in a real signed manifest carrying the
``com.doctus.*`` extension assertions, so anything entering the graph does so
through the same ingest path as prebaked media.

Same constraints as scripts/prebake_fixtures.py (probed 2026-08-26):
manifests pin ``claim_version: 1`` and signer certs need an EKU.
Requires c2pa-python; import errors surface as RuntimeError with instructions
so callers can degrade to the offline adapter cleanly.
"""
from __future__ import annotations

import json
from pathlib import Path

ODRL_CONTEXT = "http://www.w3.org/ns/odrl.jsonld"


def sign_media(src: str | Path, dst: str | Path, *, cert_pem: bytes, key_pem: bytes,
               asset_id: str, label: str = "",
               generation_model: str | None = None,
               odrl_instrument: dict | None = None,
               ingredients: list[tuple[str, str | Path]] | None = None,
               ta_url: bytes | None = None) -> Path:
    """Sign ``src`` -> ``dst`` with identity + optional generation/ODRL/ingredients.

    ``ta_url`` opts into an RFC 3161 timestamp server. It defaults to None
    (offline): timestamping needs live network access, fails closed anyway
    when unreachable, and buys nothing for demo-validity - signatures verify
    clean against the trust anchor either way.
    """
    try:
        from c2pa import Builder, C2paSigningAlg, C2paSignerInfo, Signer
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "c2pa-python is required to sign production media") from exc

    assertions: list[dict] = [
        {"label": "stds.c2pa.actions",
         "data": {"actions": [{"action": "c2pa.created"}]}},
        {"label": "com.doctus.identity",
         "data": {"asset_id": asset_id, "label": label or asset_id}},
    ]
    if generation_model:
        assertions.append({"label": "com.doctus.generation",
                           "data": {"model": generation_model,
                                    "synthid": "not_verified_in_v1"}})
    if odrl_instrument is not None:
        assertions.append({"label": "com.doctus.odrl", "data": odrl_instrument})

    # claim_version 2 trips assertion.action.malformed on current c2pa-rs;
    # v1 is what the whole toolchain round-trips cleanly (CONTEXT §4 note).
    manifest = {
        "claim_generator": "doctus-agent/0.3.0",
        "claim_version": 1,
        "assertions": assertions,
    }
    info = C2paSignerInfo(
        alg=C2paSigningAlg.PS256, sign_cert=cert_pem, private_key=key_pem,
        ta_url=ta_url)  # None => no timestamp authority (offline-safe)
    src, dst = Path(src), Path(dst)
    if dst.exists():
        dst.unlink()
    with Signer.from_info(info) as signer, Builder(json.dumps(manifest)) as builder:
        for title, ing_path in ingredients or []:
            payload = json.dumps({"title": title, "relationship": "componentOf"})
            fmt = "video/mp4" if str(ing_path).lower().endswith(".mp4") else "image/jpeg"
            with open(ing_path, "rb") as fh:
                builder.add_ingredient(payload, fmt, fh)
        builder.sign_file(str(src), str(dst), signer)
    return dst


def odrl_publish_license(*, uid: str, assigner_did: str,
                         channels: list[str], territories: list[str],
                         until: str, target: str,
                         kind_override: str | None = None) -> dict:
    """Build an ODRL 2.2 publish instrument matching the ingest mapper's grammar."""
    offer: dict = {
        "@context": ODRL_CONTEXT,
        "@type": "Offer",
        "uid": uid,
        "assigner": {"uid": assigner_did},
        "permission": [{"action": "publish", "target": target, "constraint": [
            {"leftOperand": "channel", "operator": "isSubsetOf",
             "rightOperand": channels},
            {"leftOperand": "territory", "operator": "isSubsetOf",
             "rightOperand": territories},
            {"leftOperand": "until", "operator": "lteq", "rightOperand": until},
        ]}],
    }
    if kind_override:
        offer["doctus:claimKind"] = kind_override
    return offer
