# Doctus — Design & Technical Implementation

> Companion to `CONTEXT.md` (binding decisions) and `idea.md` (concept + market).
> This document specifies **how Doctus works** at the level needed to start building.
> When code and this doc disagree, fix one of them the same day.

---

## 1. System overview

```
                        ┌─────────────────────────────────────────────────┐
                        │            Production Agent (Gemini/ADK)        │
                        │   plans shots · calls generative tools · edits  │
                        └──────┬───────────────────────┬──────────────────┘
                               │ proposed actions      │ tool results
                               ▼                       │
                    ┌─────────────────────┐            │
                    │   CLEARANCE GATE    │◄──allow/deny┘
                    │ (deterministic code)│──── deny reason (named claim)
                    └─────────┬───────────┘
                              │ O(1) lookup
                              ▼
   ┌──────────────┐   ┌─────────────────────┐   ┌──────────────────────┐
   │ RIGHTS GRAPH │──►│  POLICY COMPILER    │──►│ EFFECTIVE PERMISSIONS│
   │ signed claims│   │ intersect·narrowest │   │ (materialized, fast) │
   │ (C2PA+ext)   │   │ wins·fail-closed    │   └──────────────────────┘
   └──────┬───────┘   └─────────────────────┘
          │ gap identified                 ▲ recompile after countersign
          ▼                                │
   ┌─────────────────────┐   ┌──────────┴───────────┐
   │  NEGOTIATION AGENT  │──►│ HUMAN COUNTERSIGN    │
   │ drafts instrument   │   │ (approval = signature)│
   └─────────────────────┘   └──────────────────────┘
```

**Core principle:** compile-on-write, lookup-at-read. The expensive part (walking derivation chains, intersecting scopes) happens when claims enter or change. The gate itself is a single-row read plus a set-containment check — microseconds, no model in the loop.

## 2. Domain model

### 2.1 Rights Graph

A DAG. Nodes are **assets**; edges are **ingredient links** ("this composition consumed that asset"); every node and edge carries **signed claims**.

Claim types (v1):

| Claim | Attached to | Asserts | Signed by |
|---|---|---|---|
| `generation` | asset | model identity, prompt hash, SynthID status, timestamp | generator platform key |
| `license` | asset or edge | scope: channels × territories × window × derivative-rights | licensor key |
| `likeness-consent` | asset | person identity ref, permitted uses, window, exclusions | person/rep key |
| `music-clearance` | edge | sync+master scope for a specific use class | publisher/label key |
| `training-consent` | asset | may/may-not train (`c2pa.training-mining` compatible) | rights holder key |

Claims live inside the asset's C2PA manifest store as **extension assertions** (namespace `com.doctus.*`), so standard tooling still validates the file; Doctus-specific meaning rides in a documented extension — exactly how C2PA is designed to grow.

### 2.2 Effective Permission Set

Per asset, the compiled result:

```jsonc
{
  "asset_id": "ast_01J9...",
  "compiled_at": "2026-08-30T14:22:01Z",
  "graph_version": 47,
  "permissions": {
    "publish": { "channels": ["festival", "social"], "territories": ["US", "CA"],
                  "until": "2027-03-01", "exclusions": ["broadcast"] },
    "remix": false,
    "train_on": false,
    "license_out": false
  },
  "constraints_hash": "b3f1..."        // pins policy version used
}
```

## 3. Components

### 3.1 `graph/` — Rights Graph store

- SQLite (hackathon) behind a repository interface so ClickHouse can slot in later without touching callers.
- Tables: `assets`, `claims`, `edges(asset_id, ingredient_id, edge_claims)`, `decisions`.
- Every mutation bumps `graph_version`; compilers subscribe to version deltas.
- Manifest ingest path (implemented, `graph/ingest.py`): `c2pa-python` Reader under the Doctus trust anchor (`verify_cert_anchors` + `trust_anchors`, local trust list off) → `com.doctus.identity|generation|odrl` extension assertions parsed into typed claims (ODRL constraints → Scope) → store-level failure codes decide trust; any failure ⇒ claims stored with `trusted=False` ⇒ QUARANTINED_INPUT / UNTRUSTED_SIGNER shadowing downstream (fail-closed). Ingestion is idempotent (deterministic claim ids).
- Ingredient edges derive from native C2PA `ingredients[]`: v1 convention is that an ingredient's C2PA `title` mirrors its Doctus asset_id.
- Prebake: `scripts/prebake_fixtures.py` regenerates the demo PKI (`fixtures/pki`, DEMO-ONLY keys committed on purpose) and re-signs all media in `fixtures/media/` (JPEG+MP4), including a rogue-signed attack fixture asserting wide rights. Manifests pin `claim_version: 1`; signer certs must carry an EKU (emailProtection) or c2pa-rs rejects them. A vendored `c2patool` binary lives in `tools/` locally (gitignored).

### 3.1.1 `engine/decisions.py` — decision log (implemented P2)

- Every gate check writes one row: action (`action_json`: verb, asset, channel, territory, recipient, expected_graph_version) → claims evaluated (`claims_evaluated_json`: every claim in the ancestor closure with id/kind/signer/trust) → outcome (allow/deny, reason, detail, negotiation_hint, permissions_version). Allows log their evidence too — the insurer artifact must show why something shipped.
- Readers: `RightsGraph.decisions_for(asset_id)` / `all_decisions()`; renderer `render_report` is byte-stable for identical DB state; `summarize` feeds the ClickHouse dashboard (deny-reason histogram, per-asset counts).
- CLI: `python scripts/decision_report.py <db> [asset_id]`.
- Gate walks the ancestor closure once per check (quarantine + shadowing + explanations from a single pass); verdicts carry `decision_id` back into the log.

### 3.2 `engine/compiler.py` — Policy Compiler

Deterministic. Signature sketch:

```python
class PolicyCompiler:
    def compile_asset(self, asset_id: str) -> PermissionSet:
        """Walk ingredient closure (BFS, cycle-checked), collect verified claims,
        intersect scopes. Narrowest-scope-wins on conflict. Fail-closed."""

def intersect(scopes: list[Scope]) -> Scope:
    """channels ∩, territories ∩, until=min(), exclusions ∪,
    booleans AND. Empty intersection => permission absent."""
```

Rules (map to CONTEXT §5):
1. Collect verified claims over the full ancestor closure of the asset.
2. Intersect all license/consent scopes per permission verb.
3. Any ancestor with zero verified claims for a verb ⇒ verb absent for the whole asset.
4. Conflicts never union — narrowest wins; unions require a new countersigned claim (negotiation loop's job).
5. Expired windows prune at compile time via validity interval check against `now()`.
6. Output is pure data + `constraints_hash`; identical input ⇒ byte-identical output (golden-tested).

### 3.3 `engine/gate.py` — Clearance Gate

```python
class ProposedAction(TypedDict):
    verb: Literal["publish", "remix", "train_on", "license_out"]
    asset_id: str
    target: dict        # channel, territory, recipient, etc.

class ClearanceGate:
    def check(self, action: ProposedAction) -> GateVerdict:
        """1. load effective permissions (single row)
           2. verb present? scope covers target? window valid?
           3. write DecisionRecord; return ALLOW or DENY(reason)"""
```

Failure taxonomy (every deny maps to exactly one):

```
MISSING_MANIFEST · UNTRUSTED_SIGNER · EXPIRED_WINDOW · VERB_NOT_GRANTED
SCOPE_EXCEEDED(channel|territory) · INGREDIENT_UNCLEARED(asset_id)
QUARANTINED_INPUT(asset_id) · GRAPH_VERSION_STALE(retry-after-recompile)
```

The deny payload always carries: failed claim reference (or the missing-claim type), the minimal fix description, and a `negotiation_hint` the negotiator consumes.

### 3.4 `agents/` — Production agent + Negotiator (implemented P3)

- Production agent: Google ADK (Gemini), tools = generative ops (Veo/Imagen wrappers that auto-sign `generation` claims), edit/composite op (writes ingredient edges), and **all side-effectful verbs routed through the gate first**. The agent sees deny reasons verbatim — that's how it learns to route around gaps legally instead of prompt-fuzzing the gate (it can't; the gate doesn't negotiate).
- Negotiator: second agent. Input = `negotiation_hint`. Output = draft instrument (license request / consent extension) rendered as a human-readable diff + machine-readable claim. **Never self-signs.** Human approval in the UI writes the signed claim and triggers recompile.
- Implemented P3 (`src/doctus/agents/`): `ProductionAgent.generate/composite` sign real C2PA manifests at runtime (`agents/signing.py`; offline-safe, RFC 3161 timestamp opt-in via `ta_url`) and every side-effectful verb returns `ClearanceGate` verdicts as data. A scripted planner stands in for ADK until P4 — the propose→verdict→act/deny seam is what ADK tools will call. `Negotiator.draft_extension` maps a deny verdict to a minimal ODRL `DraftInstrument`; it never self-signs, refuses empty deal terms and generation instruments, and requires the caller to name the instrument class for scope/window denies (that choice IS the business deal). `CountersignLedger.propose/approve` is the human seam (invariant 6): APPROVE writes a trusted claim, bumps `graph_version`, invalidates compiled permissions, and records actor+instant in `countersign_log`. Double-signing raises.
- CLIs: `scripts/demo_arc.py` runs beats 1–6 (beat 6 proposes, does not sign); `scripts/countersign.py list|show|approve` performs the human approval (beats 7–8).
- Instrument-class rule (pinned by tests): an extension must be the SAME claim kind as the source's existing paperwork — same-kind unions within that source; a different kind becomes a second source and cross-source intersection collapses the chain (D5, invariant 1).

### 3.5 Partner-track glue (`mcp/`)

- **If ClickHouse (D2 primary):** mirror `assets/claims/effective_permissions/decisions` into ClickHouse Cloud via their managed MCP + native insert; gate stays on SQLite locally but *streams* decisions for analytics; demo dashboard query: *"p50 gate latency, deny reasons histogram, expiring-window alerts, chain-depth vs clearance-time."* Studio-scale story: millions of assets, sub-second permission lookup during generation loops.
- **If Parallel:** negotiator uses Search/FindAll/Task MCP to research rights holders + comparable license benchmarks and attach citations to the draft instrument.
- Either way the core never depends on partner availability — partner layer enriches; engine stands alone (demo resilience).

### 3.6 Cloud wiring (`cloud/` — implemented P4)

- `cloud/config.py`: `CloudConfig.from_env` resolves `DOCTUS_VEO_BACKEND`
  (`prebaked` default per D9 | `cloud`) plus GOOGLE_CLOUD_PROJECT/LOCATION;
  an unknown backend, or `cloud` without a concrete project, refuses loudly
  (fail-closed configuration, invariant 2 applied to ops).
- `cloud/veo.py`: `ShotBackend`s — `PrebakedShotBackend` renders placeholder
  frames (pixel content is authorization-irrelevant; the gate reads
  manifests), `CloudVeoShotBackend` calls Vertex AI Veo via google-genai
  (`generate_videos` → poll LRO → bytes/URI download). Both feed the SAME
  runtime-signing → ingest → compile → gate path: swapping the shot source
  never touches authorization.
- `cloud/studio.py`: `CloudStudio` assembles backend + ProductionAgent +
  ManifestIngester + gate + Negotiator + CountersignLedger behind one
  verdict-as-data surface (`publish` returns dicts, never raises on deny);
  `propose_draft` queues agent-drafted instruments for human approval.
- `cloud/tools.py`: the ADK tool surface — `make_tools` binds five functions
  (generate_shot, composite_shot, publish_video, check_permission,
  propose_license_extension); they are the ONLY model-callable actions. Deny
  explanations reach the model verbatim as tool results; the negotiation tool
  can propose but structurally cannot approve (invariant 6 by surface shape).
- `deploy/adk_app/agent.py`: module-level `root_agent` for `adk deploy
  agent_engine`; `deploy/README.md` carries the procedure, requirements pin
  `google-cloud-aiplatform[agent_engines,adk]`, and `deploy/iam.md` scopes a
  dedicated service account (aiplatform.user + staging-bucket objectAdmin
  only — approval stays human, outside GCP IAM).

## 4. Demo pipeline (the fixed arc, wired)

| # | Beat | Component exercised |
|---|------|---------------------|
| 1 | Veo generates shot → C2PA manifest auto-attached | generation claims, trust-listed signer |
| 2 | Mock likeness consent attached to talent asset | likeness-consent claim, countersign UI |
| 3 | Agent composites shot + festival-only music bed | ingredient edges, music-clearance claim |
| 4 | Compile → effective permissions computed | PolicyCompiler |
| 5 | Agent proposes trailer publish → **DENIED** `SCOPE_EXCEEDED(channel=trailer)` | Gate, deny explanation |
| 6 | Negotiator drafts music-license extension naming the exact gap | negotiation_hint flow |
| 7 | Human approves → claim signed → recompile → publish **ALLOWED** | countersign, incremental recompile |
| 8 | Inspector view shows full claim→decision audit trail | decisions log (insurer artifact) |

Fallback if Veo quota fails (Q2): pre-generated clips with real c2patool-signed manifests — every beat above unchanged.

## 5. Testing strategy

- **Golden fixtures** are the backbone: `fixtures/cases/*.yaml` each define a small graph + expected `PermissionSet` + expected verdicts for scripted actions. CI asserts exact equality. Target ≥ 20 cases covering: clean chain, expired window, untrusted signer, missing ingredient claim, conflicting licenses (narrowest-wins), quarantine propagation, deny→fix→allow loop.
- Property tests for `intersect`: commutative-in-effect, monotone-narrowing (adding claims never widens — CONTEXT invariant #1), idempotent.
- Gate latency budget asserted in tests (< 5 ms local lookup).
- Adversarial test: hand-crafted manifest attempting scope-widening re-sign must land in `UNTRUSTED_SIGNER`.

## 6. Build order (Aug 25 – Sep 6)

| Phase | Days | Deliverable | Exit criterion |
|---|---|---|---|
| P0 Scaffold + fixtures | Aug 25 | repo layout, fixture harness, CI | golden runner executes empty case green |
| P1 Graph + Compiler | Aug 26–27 | claims ingest (c2patool), compiler, 12 goldens | invariant tests pass; byte-stable output |
| P2 Gate + decisions | Aug 28 | gate w/ full taxonomy, decision log | <5ms verdicts; all deny reasons covered by cases. Delivered Aug 26: audit rows carry action→claims→outcome, 13 goldens, report CLI |
| P3 Agents | Aug 29–30 | production agent (ADK) routing through gate; countersign CLI/UI stub | demo beats 1–5 run end-to-end locally. Delivered Aug 26: beats 1–6 via `scripts/demo_arc.py` (runtime C2PA signing, offline-safe), beats 7–8 via `scripts/countersign.py`; agent-layer tests + negotiation-semantics goldens against real signed media |
| P4 GCP wiring | Aug 31–Sep 1 | Veo/Imagen real generations signed; deploy agent to Agent Builder; IAM scoping | beat 1 real-cloud; fallback prebaked verified too. Delivered Aug 26: `cloud/` package (config fail-closed, Veo backends, CloudStudio, ADK tool surface) + `deploy/` scaffold (Agent Engine root_agent, README, IAM); beats 1–8 verified through the wired layer on the D9 fallback — real-Veo leg awaits GCP billing (Q4) |
| P5 Partner layer | Sep 2 | ClickHouse mirror + dashboard (or Parallel negotiator enrichment per Q1) | dashboard live-querying decisions. Delivered: dual-engine ClickHouse mirror (HTTP + simulator), analytical queries (p50/p95 latency, deny histogram, risk radar), ClickHouse MCP server, terminal dashboard CLI |
| P6 Negotiator + polish | Sep 3–4 | full arc beats 6–8; inspector view; trailer video script | complete arc on camera. Delivered: automated 8-beat runner (`scripts/demo_arc_e2e.py`), interactive standalone HTML inspector (`src/doctus/inspector/` & `scripts/inspector.py`), timed 3-min video trailer script (`docs/TRAILER_SCRIPT.md`) |
| Buffer / submission | Sep 5–6 | Devpost form, license file visible, backup video | submitted ≥24h early. Delivered: MIT `LICENSE`, Devpost submission doc (`docs/DEVPOST_SUBMISSION.md`), showcase `README.md`, 64 green tests |

## 7. Threat-model notes (name in pitch)

- We inherit C2PA's honest-issuer assumption; mitigations: trust lists, fail-closed, auditable trail (cite arXiv 2604.24890 critique proactively).
- The gate is not a sandbox: it authorizes *semantics* (rights), not *safety* of pixels. Say this precisely; conflation invites expert pushback.
- Replay/stale-graph attacks handled via `GRAPH_VERSION_STALE` — actions carry the graph_version they were planned against.

## 8. YAGNI (binding for hackathon)

No marketplace/payments · no multi-tenant auth beyond demo IAM · no video-player UI (inspector = generated static report + terminal) · no blockchain anything · no language beyond English in instruments · no Windows host quirks (everything containerized/cloud).
