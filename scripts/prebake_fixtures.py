"""Prebake the demo media fixtures with REAL signed C2PA manifests (CONTEXT.md D9).

Generates (idempotently):
  fixtures/pki/            demo root CA + studio signer (DEMO-ONLY keys, committed)
  fixtures/media/*.jpg/mp4 signed assets wired for the D7 demo arc:
      ast_music_bed_v1     ODRL Offer (license): publish @ festival/US until 2027-01-01
      ast_hero_shot_v1     generation claim only (Veo-shot stand-in)
      ast_composite_v1     consumes hero_shot + music_bed as native C2PA ingredients
      ast_talent_frame_v1  ODRL Agreement (likeness_consent): publish @ social
      ast_video_shot_v1    MP4, generation claim only (format coverage)
      signed-by-rogue/ast_rogue_asset_v1.jpg  signed by a ROGUE CA asserting wide
                           rights - must land QUARANTINED at ingest (invariant 2)

Ingredient linkage uses the v1 convention: C2PA ingredient.title mirrors the
ingredient's Doctus asset_id (see src/doctus/graph/ingest.py).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKI = REPO / "fixtures" / "pki"
MEDIA = REPO / "fixtures" / "media"

ODRL_CONTEXT = "http://www.w3.org/ns/odrl.jsonld"


def sh(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True)


# --------------------------------------------------------------------- PKI
def ensure_pki() -> tuple[Path, Path, Path]:
    PKI.mkdir(parents=True, exist_ok=True)
    root_pem = PKI / "demo_root.pem"
    signer_cert = PKI / "demo_signer.pem"
    signer_key = PKI / "demo_signer.key"
    if root_pem.exists() and signer_cert.exists() and signer_key.exists():
        print("PKI: reusing existing demo certificates")
        return root_pem, signer_cert, signer_key
    print("PKI: generating demo root + studio signer")
    sh("openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "3650",
       "-nodes", "-keyout", str(PKI / "demo_root.key"), "-out", str(root_pem),
       "-subj", "/CN=Doctus Demo Root/O=Doctus Demo/C=US",
       "-addext", "basicConstraints=critical,CA:TRUE",
       "-addext", "keyUsage=critical,keyCertSign,cRLSign,digitalSignature")
    sh("openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
       "-keyout", str(signer_key), "-out", str(PKI / "demo_signer.csr"),
       "-subj", "/CN=Doctus Studio Signer/O=Doctus Demo/C=US")
    ext = ("basicConstraints=critical,CA:FALSE\n"
           "keyUsage=critical,digitalSignature\n"
           "# c2pa-rs requires an EKU; emailProtection is the conventional demo pick\n"
           "extendedKeyUsage=emailProtection\n")
    (PKI / "demo_signer.ext").write_text(ext, encoding="utf-8")
    sh("openssl", "x509", "-req", "-in", str(PKI / "demo_signer.csr"),
       "-CA", str(root_pem), "-CAkey", str(PKI / "demo_root.key"),
       "-CAcreateserial", "-out", str(signer_cert),
       "-days", "3650", "-sha256", "-extfile", str(PKI / "demo_signer.ext"))
    return root_pem, signer_cert, signer_key


def ensure_rogue_pki() -> tuple[Path, Path, Path]:
    d = MEDIA / "signed-by-rogue"
    d.mkdir(parents=True, exist_ok=True)
    root = d / "rogue_root.pem"
    leaf = d / "rogue_leaf.pem"
    key = d / "rogue_leaf.key"
    if root.exists() and leaf.exists() and key.exists():
        return root, leaf, key  # type: ignore[return-value]
    sh("openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "3650",
       "-nodes", "-keyout", str(d / "rogue_root.key"), "-out", str(root),
       "-subj", "/CN=Rogue CA/O=Not Doctus/C=US",
       "-addext", "basicConstraints=critical,CA:TRUE",
       "-addext", "keyUsage=critical,keyCertSign,cRLSign,digitalSignature")
    sh("openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
       "-keyout", str(key), "-out", str(d / "rogue_leaf.csr"),
       "-subj", "/CN=Rogue Signer/O=Not Doctus/C=US")
    (d / "rogue_leaf.ext").write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature\n"
        "extendedKeyUsage=emailProtection\n", encoding="utf-8")
    sh("openssl", "x509", "-req", "-in", str(d / "rogue_leaf.csr"),
       "-CA", str(root), "-CAkey", str(d / "rogue_root.key"),
       "-CAcreateserial", "-out", str(leaf),
       "-days", "3650", "-sha256", "-extfile", str(d / "rogue_leaf.ext"))
    return root, leaf, key


# ------------------------------------------------------------------- media
def base_jpeg(path: Path, color: tuple[int, int, int], caption: str) -> None:
    if path.exists():
        path.unlink()
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (320, 180), color)
    d = ImageDraw.Draw(img)
    d.text((10, 80), caption, fill=(255, 255, 255))
    img.save(path, format="JPEG", quality=90)


def base_mp4(path: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg required to prebake the MP4 fixture")
    if path.exists():
        path.unlink()
    sh("ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x180:rate=24",
       "-pix_fmt", "yuv420p", "-c:v", "libx264", str(path))


def actions_assertion(action: str = "c2pa.created") -> dict:
    return {"label": "stds.c2pa.actions",
            "data": {"actions": [{"action": action}]}}


def sign_file(src: Path, dst: Path, extra_assertions: list[dict],
              cert: bytes, key: bytes, ingredients: list[tuple[str, Path]] | None = None) -> None:
    """Sign src -> dst with identity + given assertions (+ optional C2PA ingredients)."""
    from c2pa import Builder, C2paSigningAlg, C2paSignerInfo, Signer
    if dst.exists():
        dst.unlink()
    manifest = {
        "claim_generator": "doctus-prebake/1.0",
        # claim_version 2 triggers assertion.action.malformed on c2pa-rs 0.90.x
        # (probed empirically); v1 is what current tooling round-trips cleanly.
        "claim_version": 1,
        "assertions": [actions_assertion(), *extra_assertions],
    }
    info = C2paSignerInfo(
        alg=C2paSigningAlg.PS256, sign_cert=cert, private_key=key,
        ta_url=b"http://timestamp.digicert.com")
    with Signer.from_info(info) as signer, Builder(json.dumps(manifest)) as builder:
        for title, ing_path in ingredients or []:
            payload = json.dumps({"title": title, "relationship": "componentOf"})
            fmt = "video/mp4" if ing_path.suffix == ".mp4" else "image/jpeg"
            with open(ing_path, "rb") as fh:
                builder.add_ingredient(payload, fmt, fh)
        builder.sign_file(str(src), str(dst), signer)


def identity(asset_id: str, label: str) -> dict:
    return {"label": "com.doctus.identity",
            "data": {"asset_id": asset_id, "label": label}}


def generation(model: str) -> dict:
    return {"label": "com.doctus.generation",
            "data": {"model": model, "synthid": "not_verified_in_v1"}}


def odrl_license(uid: str, assigner_did: str, action: str, kind_override: str | None,
                 channels: list[str], territories: list[str], until: str,
                 target: str) -> dict:
    permission: dict = {"action": action, "target": target, "constraint": [
        {"leftOperand": "channel", "operator": "isSubsetOf", "rightOperand": channels},
        {"leftOperand": "territory", "operator": "isSubsetOf", "rightOperand": territories},
        {"leftOperand": "until", "operator": "lteq", "rightOperand": until},
    ]}
    offer: dict = {
        "@context": ODRL_CONTEXT,
        "@type": "Offer",
        "uid": uid,
        "assigner": {"uid": assigner_did},
        "permission": [permission],
    }
    if kind_override:
        offer["doctus:claimKind"] = kind_override
    return {"label": "com.doctus.odrl", "data": offer}


def main() -> int:
    root_pem, signer_cert_path, signer_key_path = ensure_pki()
    cert = signer_cert_path.read_bytes()
    key = signer_key_path.read_bytes()
    MEDIA.mkdir(parents=True, exist_ok=True)

    # --- ingredients first (they get consumed as C2PA ingredients below) ----
    bed_src = MEDIA / "_src_music_bed.jpg"
    base_jpeg(bed_src, (30, 30, 120), "MUSIC BED")
    sign_file(
        bed_src, MEDIA / "ast_music_bed_v1.jpg",
        [identity("ast_music_bed_v1", "licensed music bed"),
         odrl_license("urn:doctus:license:music-bed-01", "did:key:zdoctusPublisher01",
                      "publish", None, ["festival"], ["US"], "2027-01-01T00:00:00Z",
                      "urn:doctus:asset:music-bed")],
        cert, key)
    bed_src.unlink()

    hero_src = MEDIA / "_src_hero.jpg"
    base_jpeg(hero_src, (120, 30, 30), "HERO SHOT (veo stand-in)")
    sign_file(
        hero_src, MEDIA / "ast_hero_shot_v1.jpg",
        [identity("ast_hero_shot_v1", "Veo hero shot (prebaked stand-in)"),
         generation("veo-3.0-demo")],
        cert, key)
    hero_src.unlink()

    comp_src = MEDIA / "_src_composite.jpg"
    base_jpeg(comp_src, (70, 20, 90), "COMPOSITE: hero + bed")
    sign_file(
        comp_src, MEDIA / "ast_composite_v1.jpg",
        [identity("ast_composite_v1", "composited demo shot"),
         generation("doctus-compositor-v1")],
        cert, key,
        ingredients=[("ast_hero_shot_v1", MEDIA / "ast_hero_shot_v1.jpg"),
                     ("ast_music_bed_v1", MEDIA / "ast_music_bed_v1.jpg")])
    comp_src.unlink()

    talent_src = MEDIA / "_src_talent.jpg"
    base_jpeg(talent_src, (20, 90, 40), "TALENT FRAME")
    sign_file(
        talent_src, MEDIA / "ast_talent_frame_v1.jpg",
        [identity("ast_talent_frame_v1", "talent appearance frame"),
         generation("imagen-4.0-demo"),
         odrl_license("urn:doctus:consent:talent-01", "did:key:zdoctusTalentRep01",
                      "publish", "likeness_consent", ["social"], ["US"],
                      "2027-03-01T00:00:00Z", "urn:doctus:asset:talent-frame")],
        cert, key)
    talent_src.unlink()

    vid_src = MEDIA / "_src_video.mp4"
    base_mp4(vid_src)
    sign_file(
        vid_src, MEDIA / "ast_video_shot_v1.mp4",
        [identity("ast_video_shot_v1", "prebaked video shot"),
         generation("veo-3.0-demo")],
        cert, key)
    vid_src.unlink()

    # --- the attack artifact: rogue-signed, asserting WIDE rights -----------
    _, rogue_leaf, rogue_key = ensure_rogue_pki()
    rogue_src = MEDIA / "_src_rogue.jpg"
    base_jpeg(rogue_src, (140, 100, 10), "ROGUE-SIGNED")
    sign_file(
        rogue_src, MEDIA / "signed-by-rogue" / "ast_rogue_asset_v1.jpg",
        [identity("ast_rogue_asset_v1", "wide-rights claim from an untrusted signer"),
         generation("forgery-model-v1"),
         odrl_license("urn:doctus:license:too-good", "did:key:zroguE01",
                      "publish", None, ["festival", "trailer", "social"], ["US", "EU"],
                      "2037-01-01T00:00:00Z", "urn:doctus:asset:rogue")],
        rogue_leaf.read_bytes(), rogue_key.read_bytes())
    rogue_src.unlink()

    # drop openssl byproducts we don't need to keep around
    for junk in list(MEDIA.rglob("*.csr")) + list(MEDIA.rglob("*.ext")) + list(MEDIA.rglob("*.srl")):
        junk.unlink()

    print("\nPrebaked fixtures:")
    for p in sorted(MEDIA.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(REPO)}  ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
