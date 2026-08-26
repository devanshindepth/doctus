"""C2PA ingest: signed media files -> typed claims + ingredient edges.

The bridge between real Content-Credentials files and the rights graph
(DESIGN.md §3.1 manifest ingest path). Reads each file's C2PA manifest store
under the Doctus trust anchor, maps ``com.doctus.*`` extension assertions to
typed Claims, and derives IngredientEdges from native C2PA ``ingredients``
(their ``title`` mirrors the ingredient's Doctus asset_id — declared v1
convention, see docs/DESIGN.md §3.1).

Fail-closed rules (CONTEXT.md invariant 2):
- no manifest            => nothing ingested, reported MISSING_MANIFEST
- any validation failure => claims stored with trusted=False (the gate's
  UNTRUSTED_SIGNER shadowing then quarantines every downstream chain)
- unmatched ingredients  => recorded in the report, never silently dropped

Ingestion is idempotent: claim ids are deterministic functions of manifest
identity + assertion label, and the store upserts.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

#: validation-status codes that do NOT taint trust (informational-only echoes).
BENIGN_CODES = frozenset({"ingredient.unknownProvenance"})

#: assertion labels understood by the mapper (everything else com.doctus.*
#: is reported as ignored; foreign labels are none of our business).
DOCTUS_PREFIX = "com.doctus."

_KIND_BY_TYPE = {"Offer": "license", "Agreement": "likeness_consent", "Set": "training_consent"}
_KIND_OVERRIDE_FIELD = "doctus:claimKind"


@dataclass(frozen=True)
class IngestReport:
    """What happened when one file met the graph."""

    path: Path
    asset_id: str | None
    claim_ids: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()   # (asset_id, ingredient_id)
    trusted: bool = False
    failure_codes: tuple[str, ...] = ()
    status: str = "SKIPPED"                    # INGESTED | QUARANTINED | NO_MANIFEST | SKIPPED
    notes: tuple[str, ...] = ()

    def __str__(self) -> str:  # pragma: no cover - debug convenience
        return (f"{self.status:10} {self.path.name} asset={self.asset_id} "
                f"claims={len(self.claim_ids)} trusted={self.trusted} "
                f"failures={list(self.failure_codes)}")


@dataclass
class _PendingEdge:
    asset_id: str
    ingredient_title: str


class ManifestIngester:
    """Reads signed media, maps Doctus extension assertions into the graph."""

    def __init__(self, graph, trust_anchors_pem: str | None = None) -> None:
        self.graph = graph
        self.trust_anchors_pem = trust_anchors_pem

    # ------------------------------------------------------------------ API
    def ingest_file(self, path: str | Path) -> IngestReport:
        path = Path(path)
        try:
            store = self._read_store(path)
        except Exception as exc:  # noqa: BLE001 - any read failure = no manifest
            return IngestReport(path=path, asset_id=None, status="NO_MANIFEST",
                                notes=(f"{type(exc).__name__}: {exc}",))
        return self._ingest_store(path, store)

    def ingest_directory(self, root: str | Path,
                         patterns: tuple[str, ...] = ("*.jpg", "*.jpeg", "*.webp", "*.mp4")) \
            -> list[IngestReport]:
        """Two-pass walk: register every asset first, then resolve edges."""
        root = Path(root)
        files = sorted({p for pat in patterns for p in root.rglob(pat)})
        reports: list[IngestReport] = []
        pending: list[tuple[IngestReport, list[_PendingEdge]]] = []
        for f in files:
            try:
                store = self._read_store(f)
            except Exception as exc:  # noqa: BLE001
                reports.append(IngestReport(path=f, asset_id=None, status="NO_MANIFEST",
                                            notes=(f"{type(exc).__name__}: {exc}",)))
                continue
            report = self._ingest_store(f, store, defer_edges=True)
            pending.append((report, self._pending_edges(store)))
            reports.append(report)
        # second pass: edges now that every asset exists
        resolved: list[IngestReport] = []
        for report, edges in pending:
            kept: list[tuple[str, str]] = []
            notes = list(report.notes)
            for e in edges:
                ingredient_id = self._resolve_ingredient(e.ingredient_title)
                if ingredient_id is None:
                    notes.append(f"unmatched ingredient '{e.ingredient_title}' "
                                 f"(no such asset; fail-closed: no edge)")
                    continue
                from doctus.engine.models import IngredientEdge  # noqa: PLC0415
                self.graph.add_edge(IngredientEdge(asset_id=e.asset_id, ingredient_id=ingredient_id))
                kept.append((e.asset_id, ingredient_id))
            resolved.append(IngestReport(
                path=report.path, asset_id=report.asset_id,
                claim_ids=report.claim_ids, edges=tuple(kept),
                trusted=report.trusted, failure_codes=report.failure_codes,
                status=report.status, notes=tuple(notes)))
        return resolved

    # ------------------------------------------------------------- internals
    def _read_store(self, path: Path) -> dict:
        from c2pa import Reader

        if self.trust_anchors_pem is None:
            with Reader(str(path)) as reader:
                return json.loads(reader.json())
        from c2pa import Context, Settings

        settings = Settings.from_dict({
            "verify": {"verify_cert_anchors": True, "verify_trust_list": False},
            "trust": {"trust_anchors": self.trust_anchors_pem},
        })
        with Context(settings) as ctx, Reader(str(path), context=ctx) as reader:
            return json.loads(reader.json())

    def _ingest_store(self, path: Path, store: dict, defer_edges: bool = False) -> IngestReport:
        failures = self._failure_codes(store)
        active = store.get("manifests", {}).get(store.get("active_manifest"))
        if active is None:
            return IngestReport(path=path, asset_id=None, status="NO_MANIFEST",
                                failure_codes=tuple(failures))

        trusted = not failures
        sig_info = active.get("signature_info") or {}
        signer = sig_info.get("common_name") or sig_info.get("issuer") or "unknown-signer"
        # Runtime (agent-signed) media may carry no trusted timestamp when
        # signed offline without an RFC 3161 server; the store requires a
        # non-null issued_at, so fall back to ingest time instead of
        # crashing on - or silently dropping - an otherwise valid claim.
        issued_at = _parse_time(sig_info.get("time")) or dt.datetime.now(dt.UTC)

        identity = self._find_assertion(active, DOCTUS_PREFIX + "identity")
        manifest_label = active.get("label", "")
        asset_id = (identity or {}).get("asset_id") or _asset_id_from_label(manifest_label)

        from doctus.engine.models import AssetRecord, Claim, ClaimKind  # noqa: PLC0415
        self.graph.add_asset(AssetRecord(asset_id=asset_id,
                                         label=(identity or {}).get("label", path.name)))

        claim_ids: list[str] = []
        notes: list[str] = []
        for assertion in active.get("assertions", []):
            label = assertion.get("label", "")
            if not label.startswith(DOCTUS_PREFIX):
                continue
            data = assertion.get("data")
            if label == DOCTUS_PREFIX + "identity":
                continue                      # consumed above as asset registration
            if label == DOCTUS_PREFIX + "generation":
                # provenance of origin only — authorizes nothing by itself
                # (models.py); gives fully-owned originals their covering claim.
                gen_id = f"gen-{hashlib.sha256(manifest_label.encode()).hexdigest()[:10]}"
                self.graph.add_claim(Claim(
                    claim_id=gen_id, kind=ClaimKind.GENERATION, asset_id=asset_id,
                    signer=signer, trusted=trusted, issued_at=issued_at))
                claim_ids.append(gen_id)
                continue
            if label == DOCTUS_PREFIX + "odrl":
                claim = _odrl_to_claim(data, asset_id=asset_id, signer=signer,
                                       trusted=trusted, issued_at=issued_at,
                                       manifest_label=manifest_label, assertion_label=label)
                self.graph.add_claim(claim)
                claim_ids.append(claim.claim_id)
                continue
            notes.append(f"ignored unsupported doctus assertion '{label}'")

        status = "INGESTED" if trusted else "QUARANTINED"
        report = IngestReport(path=path, asset_id=asset_id,
                              claim_ids=tuple(claim_ids), edges=(),
                              trusted=trusted, failure_codes=tuple(failures),
                              status=status, notes=tuple(notes))
        if defer_edges:
            return report
        # single-file mode: resolve edges immediately (targets may not exist yet;
        # unmatched ones are reported, never guessed)
        kept: list[tuple[str, str]] = []
        for pe in self._pending_edges(store):
            ingredient_id = self._resolve_ingredient(pe.ingredient_title)
            if ingredient_id is None:
                note = f"unmatched ingredient '{pe.ingredient_title}'"
                notes.append(note)
                continue
            from doctus.engine.models import IngredientEdge  # noqa: PLC0415
            self.graph.add_edge(IngredientEdge(asset_id=pe.asset_id, ingredient_id=ingredient_id))
            kept.append((pe.asset_id, ingredient_id))
        return IngestReport(path=path, asset_id=asset_id, claim_ids=tuple(claim_ids),
                            edges=tuple(kept), trusted=trusted,
                            failure_codes=tuple(failures), status=status,
                            notes=tuple(notes))

    @staticmethod
    def _failure_codes(store: dict) -> list[str]:
        codes: list[str] = []
        for item in store.get("validation_status") or []:
            code = item.get("code", "")
            if code and code not in BENIGN_CODES:
                codes.append(code)
        results = store.get("validation_results") or {}
        blocks = [results.get("activeManifest") or {}]
        for delta in results.get("ingredientDeltas") or []:
            blocks.append(delta.get("validationDeltas") or {})
        for block in blocks:
            for failure in block.get("failure") or []:
                code = failure.get("code", "")
                if code and code not in BENIGN_CODES:
                    codes.append(code)
        return sorted(set(codes))

    @staticmethod
    def _find_assertion(active: dict, label: str) -> dict | None:
        for assertion in active.get("assertions", []):
            if assertion.get("label") == label:
                data = assertion.get("data")
                return data if isinstance(data, dict) else None
        return None

    @staticmethod
    def _pending_edges(store: dict) -> list[_PendingEdge]:
        active = store.get("manifests", {}).get(store.get("active_manifest"))
        if active is None:
            return []
        manifest_label = active.get("label", "")
        identity = ManifestIngester._find_assertion(active, DOCTUS_PREFIX + "identity")
        asset_id = (identity or {}).get("asset_id") or _asset_id_from_label(manifest_label)
        out: list[_PendingEdge] = []
        for ing in active.get("ingredients", []):
            title = ing.get("title")
            if title:
                out.append(_PendingEdge(asset_id=asset_id, ingredient_title=title))
        return out

    def _resolve_ingredient(self, title_or_id: str) -> str | None:
        """v1 convention: ingredient.title mirrors the ingredient's asset_id."""
        if self.graph.get_asset(title_or_id) is not None:
            return title_or_id
        return None


# ------------------------------------------------------------------ mapping
def _odrl_to_claim(odrl: dict, *, asset_id: str, signer: str, trusted: bool,
                   issued_at: dt.datetime, manifest_label: str,
                   assertion_label: str) -> "Claim":
    """Map an ODRL 2.2 JSON-LD payload (D10) onto a typed Claim (Q5 vocabulary).

    - kind: explicit ``doctus:claimKind`` overrides, else ODRL @type
      (Offer->license, Agreement->likeness_consent, Set->training_consent).
    - scope: permissions are alternatives *within this instrument* => their
      channel/territory sets union; windows take the min; exclusions accumulate.
    """
    from doctus.engine.models import Claim, ClaimKind  # noqa: PLC0415
    from doctus.engine.scope import Scope  # noqa: PLC0415

    kind_name = odrl.get(_KIND_OVERRIDE_FIELD) or _KIND_BY_TYPE.get(odrl.get("@type"), "license")
    kind = ClaimKind(kind_name)

    channels: set[str] = set()
    territories: set[str] = set()
    exclusions: set[str] = set()
    valid_from: dt.datetime | None = None
    valid_until: dt.datetime | None = None

    for permission in odrl.get("permission", []) or []:
        for constraint in permission.get("constraint", []) or []:
            lo = constraint.get("leftOperand")
            op = constraint.get("operator")
            ro = constraint.get("rightOperand")
            if lo == "channel" and isinstance(ro, list):
                if op == "isSubsetOf":
                    channels.update(ro)
            elif lo == "territory" and isinstance(ro, list):
                if op == "isSubsetOf":
                    territories.update(ro)
            elif lo == "exclusion" and isinstance(ro, list):
                exclusions.update(ro)
            elif lo == "until" and isinstance(ro, str):
                until = _parse_time(ro)
                if until is not None:
                    valid_until = until if valid_until is None else min(valid_until, until)
            elif lo == "from" and isinstance(ro, str):
                start = _parse_time(ro)
                if start is not None:
                    valid_from = start if valid_from is None else max(valid_from, start)

    scope = Scope(channels=frozenset(channels), territories=frozenset(territories),
                  valid_until=valid_until, exclusions=frozenset(exclusions))
    uid = odrl.get("uid") or assertion_label
    digest = hashlib.sha256(f"{manifest_label}|{assertion_label}".encode()).hexdigest()[:10]
    claim_id = f"{_slug(str(uid))[:36]}-{digest}"
    return Claim(
        claim_id=claim_id, kind=kind, asset_id=asset_id, signer=signer,
        trusted=trusted, issued_at=issued_at, valid_from=valid_from,
        valid_until=valid_until, scope=scope, odrl=odrl,
    )


def _asset_id_from_label(label: str) -> str:
    """urn:c2pa:<uuid> -> ast_<first 12 chars>. Deterministic fallback identity."""
    tail = label.split(":")[-1] if label else "unknown"
    return f"ast_{tail[:12]}"


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text).strip("-")


def _parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def default_trust_anchors() -> str | None:
    """Doctus demo anchor, if the developer has prebaked it (scratch/, gitignored)."""
    here = Path(__file__).resolve().parent.parent.parent.parent
    candidate = here / "scratch" / "p1probe" / "root.pem"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return None
