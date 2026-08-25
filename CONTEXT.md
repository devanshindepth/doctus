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
