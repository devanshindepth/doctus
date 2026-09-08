# Devpost Submission — Doctus: Chain-of-Title as Executable Policy

**Hackathon:** Agentic Cinema (Google Cloud × Gemini Enterprise)  
**Track:** Agents for Media & Entertainment  
**Partner Track:** ClickHouse (Rights Graph & Clearance Analytics at Studio Scale)  
**Project Repository:** https://github.com/doctus-ai/doctus  
**License:** MIT (Visible in repository root)  

---

## 1. Short Pitch (Tagline)
*Chain-of-title as executable policy: cryptographic C2PA provenance-derived permissions gating autonomous AI production agents, with ClickHouse rights analytics.*

---

## 2. Inspiration & The Problem
In 2026, generative AI video production is moving at exponential speed. Autonomous production agents running on Google Cloud can generate shots with Veo, composite multi-track scenes, edit cuts, and schedule marketing distribution.

However, the legal infrastructure backing Hollywood is broken:
1. **The Insurance Cliff:** On January 1, 2026, Verisk introduced standardized endorsement forms (CG 40 47 / CG 40 48) allowing commercial insurance carriers to exclude generative-AI liabilities from entertainment policies. Without Errors & Omissions (E&O) insurance coverage, major distributors cannot touch an AI film.
2. **Statutory Damages:** Multi-studio litigation (e.g. Disney & Universal v. Midjourney) seeks up to $150,000 per statutory infringement for uncleared outputs.
3. **The Pixel Fallacy:** Existing detection tools (like CopySight AI) attempt to inspect *pixels* statistically after creation. This approach produces false positives, misses complex licensing restrictions (such as festival-only music rights or regional likeness consents), and acts only after damage has occurred.

Provenance standards like C2PA and SynthID answer *"where did this come from?"*—but nothing answered *"what may be done with this?"*

We asked the fundamental research question:
> *Can the provenance metadata that generative pipelines already emit be elevated from passive documentation into the active authorization substrate for autonomous agents—such that "is this action permitted?" becomes a mechanical evaluation over signed manifests instead of a judgment call by an LLM?*

---

## 3. What It Does (The System Architecture)
Doctus treats a media asset's provenance graph as a program, compiles that program into machine-enforceable usage permissions, and deterministically gates every agent action against those permissions.

### Core Architectural Pillars:
1. **Rights Graph (C2PA + W3C ODRL 2.2):**
   Assets carry C2PA Content Credentials with typed extension assertions (`com.doctus.*`) verified under the studio's Root PKI. Licensing terms (channels, territories, duration, likeness consents) are embedded as W3C ODRL 2.2 JSON-LD records. Native C2PA ingredient edges define the derivation DAG.
2. **Deterministic Policy Compiler:**
   Walks the asset's ancestor closure, computes the mathematical lattice intersection of rights across all ingredients, and applies conservative conflict resolution (narrowest-scope-wins, fail-closed by construction). Any unsigned, corrupted, or rogue-signed ingredient causes immediate quarantine.
3. **The Clearance Gate (Sub-5ms SLA):**
   Wraps the agent's action space. Before an action (publish, remix, export) can take effect, the gate checks compiled permissions. The evaluation is pure deterministic code with zero LLM in the decision loop:
   - Responds in **< 1.5 milliseconds** (median 1.14 ms).
   - If blocked, returns a structured diagnosis with the exact missing claim and fix path.
4. **Autonomous Negotiation Loop & Human Countersignature Seam (Invariant #6):**
   When an action is blocked (e.g., promotional trailer blocked because the music bed is licensed festival-only), a second agent drafts a minimal ODRL license extension. Crucially: **the agent structurally cannot self-sign.** Only human countersignature via the studio ledger turns a draft into a signed claim.
5. **Partner Track: ClickHouse Rights Analytics at Studio Scale:**
   While the gate runs on local SQLite for microsecond fail-closed gating, the entire rights graph, gate decisions, and countersign ledger are mirrored into **ClickHouse Cloud**. ClickHouse powers studio-wide real-time analytics:
   - Monitoring gate lookup latency percentiles (p50, p90, p95, p99).
   - Denial taxonomy histograms.
   - Proactive risk radar alerting on upcoming license window expirations.
   - Provenance chain depth vs. clearance complexity.
6. **Model Context Protocol (MCP) Server:**
   Exposes ClickHouse clearance analytics to Gemini and Google ADK agents via standardized MCP tools over stdio JSON-RPC.

---

## 4. How We Built It
- **Google Cloud & Gemini Enterprise:**
  - **Vertex AI & Veo:** Automated video generation with native C2PA manifests and SynthID tracking.
  - **Google Agent Development Kit (ADK):** Production agent planning and action dispatch, with strict tool-calling boundaries where side-effectful actions route through the Clearance Gate.
  - **Vertex AI Agent Engine:** Deployable agent container scaffold with dedicated IAM role separation (`deploy/adk_app`).
- **Cryptographic Provenance:**
  - `c2pa-python` SDK verifying manifests against X.509 certificate chains with Extended Key Usage (emailProtection).
  - Prebaked and runtime signing utilities (`agents/signing.py`).
- **Partner Integration — ClickHouse:**
  - Columnar schemas (`doctus_assets`, `doctus_claims`, `doctus_edges`, `doctus_decisions`, `doctus_countersign_log`).
  - Dual-mode architecture: connects to live ClickHouse Cloud via HTTP API, with an embedded zero-dependency ClickHouse simulator ensuring resilient offline evaluation and CI testing.
  - Custom MCP server (`doctus.mcp.clickhouse_server`).
- **Interactive Visual Inspector:**
  - Standalone HTML/CSS/SVG interactive report generator (`scripts/inspector.py`) creating audit certificates for E&O underwriters.

---

## 5. Challenges We Overcame
1. **C2PA Standard Quirks:** Discovered that current `c2pa-rs` rejects X.509 certificates lacking Extended Key Usage (EKU) and fails on `claim_version: 2` action assertions. We engineered a RFC 3161-compliant demo PKI pinned to `claim_version: 1`.
2. **Cross-Source Scope Intersection:** Establishing formal semantics for license composition. We proved that extensions must match the existing paperwork's claim kind: same-kind unions within a source, while cross-source intersections conservatively collapse conflicting terms.
3. **Strict Human-in-the-Loop Boundaries:** Designing the ADK tool layer so the LLM cannot approve its own contracts. Approval requires a state mutation in the ledger by an authorized human key.
4. **Microsecond Latency Budget:** Maintaining sub-5ms gate evaluation while computing BFS closures over deep ingredient graphs. We achieved median latencies of ~1.14 ms.

---

## 6. Accomplishments We're Proud Of
- **Zero LLM Discretion on Clearance:** Permissions are calculated mechanically from cryptographically signed claims. An LLM cannot be prompt-fuzzed into approving an uncleared asset.
- **The Complete 8-Beat Demo Arc:** A single end-to-end command (`uv run python scripts/demo_arc_e2e.py`) executes generation, likeness clearance, composition, festival publish, trailer gate denial, ODRL draft proposal, human countersignature, and final clearance.
- **ClickHouse Analytics Depth:** Real-time percentile latency monitoring and proactive license risk detection across multi-level provenance graphs.
- **64 Green Tests:** Comprehensive test suite covering golden cases, scope lattice properties, latency SLA, C2PA ingest, cloud wiring, ClickHouse mirror, MCP tools, and inspector generation.

---

## 7. What We Learned
- Provenance is only as good as the trust anchor. Without strict signer validation and fail-closed taint propagation, rogue manifests can assert wide rights.
- Film clearance is essentially a capability security and programming language type problem: assets are types, compositing is casting, and licensing is scope attenuation.
- Insurability is the critical budget line for agentic cinema in 2026.

---

## 8. What's Next for Doctus
- Integrating directly with live NLE timelines (DaVinci Resolve / Premiere Pro) via OpenTimelineIO.
- Smart contract escrow for automated micropayments upon human countersignature.
- Live E&O broker API integration for instantaneous commercial policy binding.

---

## Built With
`python`, `google-cloud-vertex-ai`, `google-adk`, `gemini-pro`, `veo-2`, `clickhouse`, `c2pa`, `odrl-2.2`, `sqlite`, `mcp`, `pytest`, `hypothesis`
