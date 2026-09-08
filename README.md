# Doctus — Chain-of-Title as Executable Policy

[![Tests](https://img.shields.io/badge/tests-72%20passed-2ea043.svg)](file:///d:/coding/doctus/tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Track](https://img.shields.io/badge/Google%20Cloud-Agentic%20Cinema-4285F4.svg)](https://agentic-cinema.devpost.com/)
[![Partner Track](https://img.shields.io/badge/Partner%20Track-ClickHouse-FFCC00.svg)](https://clickhouse.com/)

---

## 🚀 Dashboard — Quickstart (2 commands)

The premium management dashboard ships with pre-seeded demo data covering the full 8-beat arc (deny → negotiate → countersign → allow).

```bash
# 1. Install dashboard dependencies (one-time)
uv sync --group dashboard

# 2. Launch — opens your browser automatically
uv run python scripts/serve_dashboard.py
```

Dashboard opens at **http://localhost:8000** · API docs at **http://localhost:8000/docs**

### What judges will see

| Panel | Demo content |
|---|---|
| **Overview** | Live KPIs — clearance rate, gate p50 latency (≤5ms SLA), asset count, pending approvals |
| **Assets** | 8 pre-loaded assets with C2PA claims, ingredient edges, compiled permissions |
| **Rights Graph** | Interactive force-directed DAG — drag to pan, hover for claim details |
| **Gate Check** | 8 one-click demo scenarios covering every deny reason + allowed cases |
| **Audit Log** | Every gate decision with full C2PA claim closure evidence, expand/collapse |
| **Countersign** | Pending broadcast extension draft + approved trailer extension with ODRL payload |
| **Analytics** | ClickHouse latency bars, denial taxonomy, chain-depth scatter, expiring licenses |
| **E&O Certificate** | Machine-generated compliance artifact with all 6 invariants verified |

### Hot-reload for development

```bash
uv run python scripts/serve_dashboard.py --reload
```

### Reset demo data

```bash
Remove-Item doctus_dashboard_demo.db   # Windows PowerShell
rm doctus_dashboard_demo.db            # macOS / Linux
uv run python scripts/serve_dashboard.py
```

---

> **The Clearance Engine:** A system that treats a media asset's provenance graph — its C2PA Content Credentials chain of who generated what, from which licensed ingredients, under which model terms — as an executable program, compiles that program into machine-enforceable usage permissions, and deterministically gates every action an AI production agent takes.

---

## The Problem: AI Cinema vs. The Liability Wall

In 2026, AI video pipelines move at machine speed. Autonomous production agents running on Google Cloud can generate shots with **Veo**, composite multi-track scenes, and schedule marketing distribution.

However, the legal infrastructure is frozen:
1. **The Insurance Cliff:** On Jan 1, 2026, Verisk introduced standardized endorsement forms (**CG 40 47 / CG 40 48**) allowing commercial insurers to exclude generative-AI liabilities. Without Errors & Omissions (E&O) coverage, major distributors will not touch an AI production.
2. **Statutory Damages:** Multi-studio litigation (e.g., Disney & Universal v. Midjourney) seeks up to **$150,000 per statutory infringement** for uncleared content.
3. **The Pixel Fallacy:** Existing detection tools attempt to inspect *pixels* statistically after generation. They guess with false positives, miss channel/territory licensing restrictions, and act only after damage occurs.

**Doctus solves this at the root:**
The LLM may *propose* actions; only valid cryptographically signed credentials *authorize* them. **Fail-closed by construction.**

---

## Architecture Overview

```
                        ┌─────────────────────────────────────────────────┐
                        │        Production Agent (Google ADK / Gemini)   │
                        │   plans shots · calls generative tools · edits  │
                        └──────┬───────────────────────┬──────────────────┘
                               │ proposed actions      │ tool results
                               ▼                       │
                    ┌─────────────────────┐            │
                    │   CLEARANCE GATE    │◄──allow/deny┘
                    │ (deterministic code)│──── deny reason (exact missing claim)
                    └─────────┬───────────┘
                              │ < 5 ms SLA (p50: 1.14 ms)
                              ▼
   ┌──────────────┐   ┌─────────────────────┐   ┌──────────────────────┐
   │ RIGHTS GRAPH │──►│   POLICY COMPILER   │──►│ EFFECTIVE PERMISSIONS│
   │ C2PA + ODRL  │   │  lattice meet · min │   │ (materialized cache) │
   │ (SQLite store│   │  fail-closed algebra│   └──────────────────────┘
   └──────┬───────┘   └─────────────────────┘
          │ gap identified                 ▲ recompile after countersign
          ▼                                │
   ┌─────────────────────┐   ┌──────────┴───────────┐
   │  NEGOTIATION AGENT  │──►│  HUMAN COUNTERSIGN   │
   │ drafts ODRL 2.2 ext │   │ (approval = signature)
   └─────────────────────┘   └──────────────────────┘
          │                              │
          ▼                              ▼
   ┌────────────────────────────────────────────────┐
   │         CLICKHOUSE ANALYTICS MIRROR            │
   │  real-time latency · deny histogram · risk radar│
   └────────────────────────────────────────────────┘
```

### Core Invariants:
1. **No Widening:** Compiling claims can only narrow or confirm permissions, never create new ones ungrounded in signed claims.
2. **Fail-Closed:** Missing manifests, untrusted signers, or expired windows trigger immediate denial. Silent allow is impossible.
3. **Every Deny Explains Itself:** Denials name the exact failed claim, ingredient ID, and cure path.
4. **Deterministic Core:** Same graph + same policy version $\rightarrow$ byte-identical permissions and audit trail.
5. **Audit Artifact:** Every decision logs `action -> claims evaluated closure -> outcome` for E&O underwriters.
6. **Human Countersignature Seam:** Agents may *draft* licenses; only human signatures turn them into graph-valid claims.

---

## The Canonical 8-Beat Demo Arc

| Beat | Action | Component Exercised | Outcome |
|:----:|:-------|:-------------------|:--------|
| **1** | Veo generates hero shot | `CloudStudio` / `c2patool` runtime signer | Signed C2PA manifest ingested trusted |
| **2** | Talent likeness publish | Likeness consent assertion | **ALLOWED** on social channel |
| **3** | Composite hero shot + music bed | Ingredient derivation edges | C2PA edges signed; music bed is festival-only |
| **4** | Festival distribution | Policy Compiler lattice meet | **ALLOWED** on festival channel |
| **5** | Trailer public publish | Clearance Gate | **DENIED**: `SCOPE_EXCEEDED` (named gap on `ast_music_bed_v1`) |
| **6** | Autonomous negotiation | Negotiator / ADK tool | ODRL 2.2 extension drafted as `PENDING` (cannot self-sign) |
| **7** | Human countersignature | Studio Lead approval in ledger | Signed claim added; graph bumped; cache invalidated |
| **8** | Re-attempt trailer publish | Clearance Gate re-evaluation | **ALLOWED**! Audit artifact exported to ClickHouse & HTML |

---

## Quickstart (Under 60 Seconds)

### 1. Launch the Studio OS Web Dashboard (Recommended for Judges)
Experience the full unicorn-tier SaaS interface with Tailwind CSS dark/red theme and Lucide SVG icons:
```bash
uv run python scripts/studio_server.py --port 8080 --open
```
Open **[http://localhost:8080](http://localhost:8080)** to:
- **Use the Judges' Demo Controller:** 1-Click "Auto-Play Full Arc" or step-by-step beat execution.
- **Run Live Clearance Preflights:** Select any asset, channel, and territory to get instant Allow/Deny verdicts with plain-English diagnoses.
- **Approve Human Countersignatures:** Review agent-drafted ODRL contracts and countersign with a single click.
- **Inspect Live ClickHouse Analytics:** Real-time latency SLA ($p50 \approx 1.14\text{ ms}$), denial histograms, and risk radar.
- **Export E&O Certificates:** One-click generation of verifiable clearance certificates for film insurers.

### 2. Run the Full Test Suite (66 Green Tests)
```bash
uv run pytest
```

### 3. Run the Canonical 8-Beat Demo Arc via CLI
```bash
uv run python scripts/demo_arc_e2e.py
```

### 4. View the ClickHouse Analytics Terminal Dashboard
```bash
uv run python scripts/analytics_dashboard.py
```

---

## Partner Track: ClickHouse Rights Analytics

At studio scale with millions of assets and multi-tier derivation chains, rights evaluation generates high-volume analytical telemetry. Doctus integrates **ClickHouse** as its high-performance columnar analytics partner.

### Dual-Engine Resilience (D9 / CONTEXT.md §3.5)
- **Production Mode:** Streams gate decisions and rights updates directly to ClickHouse Cloud via HTTP API (`CLICKHOUSE_HOST`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`).
- **Offline / CI Mode:** Zero-dependency, embedded in-process ClickHouse simulator providing exact query semantics without external services.

### Studio Analytics Supported:
1. **Gate Latency SLA Monitoring:** Quantiles (`p50`, `p90`, `p95`, `p99`) asserting our sub-5ms lookup budget.
2. **Denial Taxonomy Breakdown:** Real-time histograms of clearance failure modes (`SCOPE_EXCEEDED`, `UNTRUSTED_SIGNER`, etc.).
3. **Expiring Window Risk Radar:** Proactive alerts on licenses and likeness consents expiring within 30/60 days.
4. **Provenance Chain Depth Analysis:** Correlating asset ancestor depth with clearance clearance complexity.
5. **Executive Insurability Summary:** Clearance pass rates and E&O audit aggregates.

### ClickHouse Model Context Protocol (MCP) Server
Agents can interrogate ClickHouse directly via standard MCP tools:
```bash
# Launch stdio JSON-RPC MCP server
uv run python -m doctus.mcp.clickhouse_server
```

Tools exposed:
- `doctus_query_decisions`: Search historical decisions by asset, status, or verb
- `doctus_gate_metrics`: Query median and tail latencies
- `doctus_deny_reasons`: Fetch denial histogram
- `doctus_expiring_licenses`: Query proactive expiration alerts
- `doctus_chain_depth`: Analyze DAG depth metrics
- `doctus_executive_summary`: Get studio health snapshot

---

## Google Cloud & Vertex AI Deployment

Doctus is engineered for **Google Cloud**:
- **Clearance Studio on Google Cloud Run:** Production container packaging the unified FastAPI engine and compiled React SPA.
  ```bash
  # Deploy Studio directly to Google Cloud Run:
  export GOOGLE_CLOUD_PROJECT="your-project-id"
  ./deploy/deploy_cloud_run.sh
  ```
  *(Windows PowerShell: `.\deploy\deploy_cloud_run.ps1 -ProjectId "your-project-id"`)*

- **Veo / Imagen Backends (`src/doctus/cloud/veo.py`):** Pluggable generator backends (Cloud Vertex AI `generate_videos` API or offline prebaked fixtures) that feed the same C2PA signing and ingestion pipeline.
- **ADK Tool Layer (`src/doctus/cloud/tools.py`):** Five deterministic Python tools (`generate_shot`, `composite_shot`, `publish_video`, `check_permission`, `propose_license_extension`) bound to an `LlmAgent`.
- **Deployable Scaffold (`deploy/adk_app`):** Ready-to-deploy module for Vertex AI Agent Engine with dedicated IAM scoping (`deploy/iam.md`).


---

## Repository Structure

```
doctus/
├── src/doctus/
│   ├── agents/          # Production agent, runtime C2PA signing, Negotiator, Countersign Ledger
│   ├── analytics/       # ClickHouse mirror, schema, HTTP client, and analytical queries (P5)
│   ├── cloud/           # Google Cloud & ADK tools, Veo backends, CloudStudio (P4)
│   ├── engine/          # Policy Compiler, Clearance Gate, Scope algebra, Decision log
│   ├── graph/           # Rights Graph store (SQLite), C2PA manifest ingestion
│   ├── inspector/       # Standalone HTML Visual Inspector generator (P6)
│   └── mcp/             # ClickHouse Model Context Protocol (MCP) server
├── scripts/
│   ├── demo_arc_e2e.py  # Canonical 8-beat automated demo runner
│   ├── analytics_dashboard.py # ClickHouse terminal analytics dashboard
│   ├── inspector.py     # HTML inspector report generator & local HTTP server
│   └── countersign.py   # Human countersignature CLI seam
├── fixtures/            # Golden C2PA signed media, demo PKI certificates, test cases
├── deploy/              # Vertex AI Agent Engine deployment configuration & IAM
├── docs/
│   ├── DESIGN.md        # Technical architecture specification
│   ├── DEVPOST_SUBMISSION.md # Hackathon submission document
│   └── TRAILER_SCRIPT.md # Timed 3-minute video demo script
├── tests/               # 64 unit, property, and end-to-end integration tests
├── LICENSE              # MIT Open Source License
└── pyproject.toml       # Python package configuration (uv)
```

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
