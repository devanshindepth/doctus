# Doctus — Context (binding working memory)

> This file is **binding working memory**. Read it fully before touching anything.
> It states what Doctus is, what is decided, what is open, and what must never change.
> Keep it current: every decision that affects later work gets recorded here the day it is made.

---

## 1. What Doctus is

**One-line:** *Chain-of-title as executable policy.*

Doctus treats a media asset's provenance graph — its C2PA-style Content Credentials chain of who generated what, from which licensed ingredients, under which model terms — as a program, compiles that program into machine-enforceable usage permissions, and deterministically gates every action an AI production agent takes (generate, composite, publish, license-out).

The LLM may *propose* actions; only valid signed credentials *authorize* them. Fail-closed by construction.

**Research question (the thesis):**
> Can provenance metadata that generative pipelines already emit be elevated from passive documentation into the active authorization substrate for autonomous agents — such that "is this action permitted?" becomes a mechanical evaluation over signed manifests instead of a judgment call by an LLM?

## 2. Target venue & constraints

- **Hackathon:** Agentic Cinema (Google Cloud × Gemini Enterprise), Devpost. Ends **2026-09-07**.
- Hard requirements: functional agent on Google Cloud Agent Builder powered by Gemini + one partner track (IBM / Grafana / **Parallel** / ClickHouse / Replit); real media & entertainment workflow; deterministic multi-step behavior; public repo with visible OSS license; 3-minute trailer video.
- Judging: Technological Implementation (Cloud+partner depth) · Design · Potential Impact · Quality of the Idea.
- Brief archived at: https://web.archive.org/web/20260720232644/https://agentic-cinema.devpost.com/
- Full concept + market/competitor analysis: see `idea.md` in this repo root.

## 3. Decided (do not relitigate)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Product name is **Doctus** | Chosen by owner |
| D2 | Partner track: decide between **ClickHouse** (primary rec: rights graph = real-time analytics) and **Parallel** (negotiation/market leg). Pick ONE for submission | Both map cleanly; ClickHouse is the deeper "Technological Implementation" story |
| D3 | Enforcement is deterministic code, never model-judged | The entire novelty claim collapses if an LLM decides permissions |
| D4 | Fail-closed default everywhere; unsigned/unmanifested inputs quarantine | Insurability narrative depends on conservative semantics |
| D5 | Narrowest-scope-wins on license intersection conflicts | Conservative intersection = defensible to lawyers |
| D6 | v1 languages/formats: MP4/WebP/JPEG via c2patool; ODRL-JSON license assertions | c2patool SDK is mature; ODRL keeps licenses machine-readable without custom schema sprawl |
| D7 | Demo arc (fixed): Veo shot → attach mock likeness consent → composite music bed licensed festival-only → agent tries trailer publish → BLOCKED with named missing claim → negotiation drafts extension → human approves → publish passes | One arc demonstrates derive→gate→explain→fix |
| D8 | Partner track = **ClickHouse** | Owner call (A1): rights graph as real-time analytics is the deepest Technological Implementation story |
| D9 | Demo pipeline is built on **pre-baked c2patool-signed assets**; real-Veo wiring only as a P4 stretch if GCP billing is confirmed | Owner call (A2): demo resilience beats cloud risk |
| D10 | Instrument language = **W3C ODRL 2.2** for licenses AND likeness-consents, embedded in C2PA manifests as JSON-LD extension assertions | Owner call (A3): adopt an existing standard, not custom schema; AgentODRL shows tooling exists |

## 4. Open questions (resolve before build)

- Q4: Real-Veo stretch beat needs GCP billing/quota confirmation — only relevant if time remains after P5. *(Owner decision, non-blocking)*
- ~~Q5~~ **Pinned** (P0): ODRL action vocabulary frozen in `src/doctus/engine/models.py` (`CLAIM_VERBS`): license→{publish,remix,license_out}, likeness_consent/music_clearance→publish, training_consent→train_on.

### Known v1 simplifications (declared, not hidden)
- Deny records do not yet prune union branches (deny-dominance is v2). Union only merges positive same-source grants; a deny can never widen.
- Trust model = static signer trust-list flag on claims; real cert-chain validation against C2PA trust lists arrives with c2patool ingest (P1).
- Gate compiles fresh per check (correctness-first); materialized cache is written for analytics but not yet read back (latency already <5 ms).
- Verb mapping is claim-KIND-level (Q5 pin): an ODRL instrument mapped to `license` grants {publish, remix, license_out} across its whole scope; per-ODRL-action narrowing inside one instrument is v2.
- Prebaked manifests pin C2PA `claim_version: 1` — version 2 trips `assertion.action.malformed` on current c2pa-rs (probed 2026-08-26).

## 5. Non-negotiables (invariants)

1. **No widening:** compilation of claims can only ever narrow or confirm permissions, never create new ones not grounded in a signed claim.
2. **Fail-closed:** any verification failure, missing manifest, unknown signer, expired window ⇒ deny with explanation. Silent allow is the cardinal bug.
3. **Every deny explains itself:** the reason names the exact failed/missing claim and the fix path. A wall is not a product; a worklist is.
4. **Deterministic core:** same graph + same policy version ⇒ same permission set. Reproducible, testable with golden fixtures.
5. **Audit artifact:** every gate decision writes a record linking action → claims evaluated → outcome. The trail IS the product for insurers/E&O.
6. **Human countersigns instruments:** the negotiation agent may *draft* licenses/consents; only a human approval turns one into a graph-valid signed claim.

## 6. Repository conventions

- Python 3.12+, uv for env management, pytest everywhere logic exists.
- Layout (target): `engine/` (compiler+gate), `graph/` (rights graph store), `agents/` (production agent + negotiator), `mcp/` (partner-track server glue), `fixtures/` (golden C2PA manifests + expected verdicts), `docs/` (this file's siblings).
- Golden-fixture tests are the regression backbone: fixture manifest set + expected permission sets + expected gate verdicts, asserted byte-for-byte.
- Commits conventional (`feat:`, `fix:`, `docs:`); main stays green.
- Runtime artifacts (demo outputs, scratch manifests) live in `scratch/` — gitignored.

## 7. Key external facts (with sources in idea.md)

- C2PA verifies integrity, not truth, and enforces nothing — that gap IS the product. Formal-methods critique exists (arXiv 2604.24890); cite honestly.
- Verisk CG 40 47/48 endorsements (Jan 1 2026): carriers can exclude GenAI losses → insurability is the budget line.
- CopySight AI = closest competitor (pixel detection post-hoc). Our line: they classify pixels after generation; we verify credentials before action. Never pitch as "better detection."
- Veo/Imagen output ships C2PA+SynthID by default → native raw material on GCP.
- MCP discussion #3225 proposes carrying C2PA credentials in MCP metadata — cite as tailwind; do not depend on it shipping.

## 8. Session log

- **2026-08-24:** Concept researched, verified, saved (`idea.md`). Project created. Design written (`docs/DESIGN.md`). Next: resolve Q1–Q3, then scaffold engine skeleton.
- **2026-08-25:** P0 scaffold: engine skeleton (scope algebra, compiler, gate, graph store), 10 goldens, property+latency tests, CI. Q5 pinned in `models.py`.
- **2026-08-26:** Owner calls recorded (A1–A4 ⇒ D8–D10). **P1 delivered:** `c2pa-python` 0.37 + vendored `c2patool` 0.27 (tools/, gitignored); `graph/ingest.py` maps signed manifests (`com.doctus.identity|generation|odrl`) to typed claims under the Doctus trust anchor; edges derive from native C2PA ingredients (their `title` mirrors the ingredient asset_id); rogue-signed fixture quarantined end-to-end (`signingCredential.untrusted` → QUARANTINED_INPUT / UNTRUSTED_SIGNER shadowing); 6 prebaked media fixtures + demo PKI committed (`fixtures/pki` keys are DEMO-ONLY by design); 12 golden cases; suite 19 green. Signer certs need EKU (emailProtection) or c2pa-rs rejects them.
- **2026-08-26 (day 3, P2):** Gate + decisions delivered ahead of schedule. Decisions are now a real audit artifact (invariant 5): every check — allows included — writes action (`action_json`) → claims evaluated (full ancestor closure, `claims_evaluated_json`) → outcome (+ channel/territory/negotiation_hint); verdicts carry `decision_id`. Gate walks the closure once per check (quarantine + untrusted-shadowing + absent-verb explanations from a single pass). New `engine/decisions.py`: byte-stable report renderer, JSONL mirror, dashboard `summarize`; read-back via `RightsGraph.decisions_for/all_decisions`; CLI `scripts/decision_report.py`. Golden 13 pins MISSING_MANIFEST and keeps it distinct from VERB_NOT_GRANTED; harness now fails any case whose decision rows lack audit payload; taxonomy test proves 7 reasons through the gate + case 04 covers UNTRUSTED_SIGNER. Suite 26 green incl. <5 ms latency budget. Note: EXPIRED_WINDOW requires the lapse to ride on the compiled Scope — claim-level expiry is pruned at compile time and reads as VERB_NOT_GRANTED.
- **2026-08-26 (day 5, P4):** Cloud wiring delivered as seams-first (no GCP billing/ADC on this machine — Q4 still open), per D9 and P4's own fallback clause. New `src/doctus/cloud/`: `config.py` (`CloudConfig.from_env`; unknown backend or `cloud`-without-project refuses loudly), `veo.py` (`PrebakedShotBackend` placeholder frames vs `CloudVeoShotBackend` via google-genai `generate_videos`→LRO poll→bytes/URI; both feed the SAME sign→ingest→compile→gate path, so the shot source never touches authorization), `studio.py` (`CloudStudio.create` assembles the whole stack; publish returns verdict-as-dict, never raises on deny; `propose_draft` queues agent drafts for humans), `tools.py` (the five ADK tool functions = the only model-callable surface; negotiation tool proposes into the countersign queue and structurally cannot approve). New `deploy/`: `adk_app/agent.py` exposes module-level `root_agent` for `adk deploy agent_engine`, README with the verified command shapes, requirements pinning `google-cloud-aiplatform[agent_engines,adk]`, iam.md scoping a dedicated SA (aiplatform.user + staging-bucket objectAdmin only; approval stays human, outside IAM). pyproject gains optional `adk`/`gcp` groups — the offline core never imports Google SDKs. Verification went beyond the 13 new tests: ran the wired arc end-to-end (`scripts/demo_arc_p4.py --keep`) and closed beats 7–8 by hand on the kept workspace (deny #3 → countersign approve → retry ALLOWED #4) — first run of a day where the full 8-beat arc executed through one layer. Gotcha worth keeping: an ADK tool that "returns" a draft without writing it to the ledger leaves the human approval queue empty; propose is a state change, not a return value.
- **2026-08-26 (day 4, P3):** Agents layer delivered, exit criterion met ahead of schedule. New `src/doctus/agents/`: `ProductionAgent` (generate/composite sign REAL C2PA manifests at runtime via `agents/signing.py`; publish routes through the gate and returns verdicts as data; scripted planner stands in for ADK until P4), `Negotiator` (deny verdict → ODRL `DraftInstrument`; never self-signs, refuses empty terms/generation instruments; instrument class for scope/window denies is a caller-supplied deal term because the verdict cannot know it), `CountersignLedger` (`propose/approve` = invariant-6 human seam; APPROVE writes trusted claim + bumps graph_version + invalidates compiled permissions; double-sign raises typed errors; full history in `countersign_log`). Exit run: beats 1–5 end-to-end on prebaked media via `scripts/demo_arc.py`, which also proposes the beat-6 draft; `scripts/countersign.py list|show|approve` closes beats 7–8 (verified: deny #3 → approve → retry ALLOWED with the countersigned claim visible in the audit row). Two engine fixes fell out of the end-to-end run: (1) ingest falls back to ingest-time `issued_at` when a manifest lacks a signature timestamp (offline runtime signing produced `Claim(issued_at=None)` that crashed the store); (2) gate verb-absent explanations now mirror compiler coverage semantics — generation-only ancestors count as covered, so hero-shot chains read SCOPE_EXCEEDED instead of a bogus INGREDIENT_UNCLEARED. Semantic pin (tests against real signed media): an extension must be the SAME claim kind as the source's existing paperwork — same-kind unions within source; different kind = second source = cross-source intersection collapses the chain. Signing defaults to no RFC 3161 server (`ta_url=None`); signatures validate clean under the demo anchor either way. Suite 43 green.
- **2026-08-27 (day 6, P5):** ClickHouse partner track delivered (`src/doctus/analytics/` & `src/doctus/mcp/`). Schema mirrors `doctus_assets`, `doctus_claims`, `doctus_edges`, `doctus_decisions`, and `doctus_countersign_log`. Dual-engine architecture: connects to ClickHouse Cloud via HTTP API, with an embedded, zero-dependency ClickHouse simulator ensuring resilient offline evaluation and CI testing. Analytical queries implement latency quantiles (p50: 1.14ms vs <5ms SLA), denial taxonomy histograms, proactive expiring window risk alerts, and chain depth analysis. Full Model Context Protocol (MCP) server (`doctus.mcp.clickhouse_server`) exposes tools to Gemini and ADK agents. Terminal dashboard `scripts/analytics_dashboard.py`. Suite 50 green.
- **2026-08-28 (day 7-8, P6):** Canonical 8-beat automated demo arc delivered (`scripts/demo_arc_e2e.py`), executing generation -> likeness clearance -> composition -> festival allow -> trailer deny -> ODRL negotiation proposal -> human countersignature -> re-publish allow end-to-end. Interactive Visual Inspector generator (`src/doctus/inspector/` & `scripts/inspector.py`) outputs standalone HTML report with interactive DAG, gate timeline, evaluated ancestor closures, and verifiable E&O Insurability Certificate. Timed 3-minute video trailer script committed (`docs/TRAILER_SCRIPT.md`). Suite 64 green.
- **2026-08-28 (day 9, submission buffer):** Hackathon submission package delivered. Visible open-source MIT `LICENSE` committed. Comprehensive Devpost submission document (`docs/DEVPOST_SUBMISSION.md`) covering all judging criteria. Showcase top-level `README.md` with system architecture diagrams, quickstart, and partner deep-dive. Entire test suite (64 tests) passing in ~2.2s. Ready for submission.

