# The Clearance Engine

### A research concept for Agentic Cinema (Google Cloud × Gemini Enterprise, ends Sep 7 2026)

---

## 1. The one-line idea

> **The Clearance Engine: a system that treats a media asset's provenance graph — its C2PA-style Content Credentials chain of who generated what, from which licensed ingredients, under which model terms — as a *program*, compiles that program into machine-enforceable usage permissions, and gates every action an AI production agent takes (generate, composite, publish, license-out) against those permissions deterministically.**

It is a **concept**: a research question plus a system design. Not a build plan.

**Research question:** *Can the provenance metadata that generative pipelines already emit be elevated from passive documentation — something a human reads after the fact — into the active authorization substrate for autonomous agents, such that "is this action permitted?" becomes a mechanical evaluation over signed manifests instead of a judgment call by an LLM?*

The slogan version, for people who know film law: **chain-of-title as executable policy.**

Three properties make this land with experts:

1. **Permissions are derived, not asserted.** Every allow/deny traces to specific signed claims in the asset graph (a license manifest, a likeness consent record, a training-consent assertion). The agent never decides what's clearable — the engine evaluates, the agent obeys.
2. **Fail-closed by construction.** No manifest → no permission → blocked (with an explanation of exactly which claim is missing). An LLM can *propose* actions; only valid credentials *authorize* them.
3. **Compositional inheritance.** Permissions compose through derivation chains like types compose through casts — a clip's clearance is computed from the intersection of its ingredients' licenses, so rights analysis scales with pipeline depth instead of becoming human triage at every step.

---

## 2. Why now — three fronts converged in the last ~18 months

**(a) Provenance became machine-readable and ubiquitous — but stayed inert.**
C2PA 2.x is now embedded by default in Gemini/Veo output (plus SynthID watermarks), OpenAI images/video, Adobe Firefly, and camera firmware from Leica/Sony/Nikon/Canon [3][4][5]. Google ships a Cloud AI Content Detection API on Gemini Enterprise Agent Platform for verifying SynthID-watermarked content [4]. Crucially, the ecosystem itself states the limit: C2PA verification "confirms the manifest's integrity — not the truth of the content itself," and says nothing about what you may *do* with an asset [3]. Provenance answers "*where did this come from?*" — nobody has made it answer "*what may be done with this?*"

**(b) The transport layer for provenance-carrying agents is being drafted right now — without an enforcement story.**
MCP discussion #3225 (2026), opened by a C2PA working-group member, proposes a standard `org.c2pa/credential` meta key so tool results, prompts, and resources inside MCP can carry verifiable manifests. Their own words: "A server attaching a credential attests nothing by itself; the security value comes entirely from client-side validation." [2] In other words: the pipes are being standardized; the *decision procedure* those pipes should enable does not exist. Existing MCP servers in this space are readers — they return plain-language provenance summaries for humans; they decide nothing [3].

**(c) Agent governance research exists — but all of it sources policy from authored text, never from asset provenance.**
The 2025–26 wave compiles natural-language/company policy into runtime guards (e.g., build-time compilation of policy documents into verifiable guard code around tool calls, τ-bench Airlines domain [9]) and enforces behavioral specs over agent skills (VIGIL: policies from "skill specifications, operator-defined constraints, global rules") [10]. AgentODRL shows LLMs can now reliably author ODRL machine-readable rights policies from prose [8] — but from *prose*, not from signed provenance chains. Provenance-based access control is an old academic idea (Prov-PBAC lineage, 2010–2014; IPBAC 2026 uses interaction logs) [11] — none of it touches C2PA-style content-provenance graphs or generative-media licensing. And the one 2026 paper combining multi-agent creation with copyright/provenance only *writes* watermarks on outputs; it never *reads* provenance back as input to decisions [7].

Each front stops exactly one step short of the others' territory. The intersection is empty.

---

## 3. System design (concept level)

Four components:

**1. Rights Graph (the ledger of signed claims).**
Every asset carries (or references) a manifest store: generation events (model identity, prompt hash, SynthID status), ingredient links (which assets fed this composition), and *license assertions* — ODRL-flavored records attached at creation or negotiation time: territory windows, channel scope, duration caps, likeness consent scope, derivative-works flags, training-mining opt-outs (C2PA already reserves `training-mining` assertions).

**2. Policy Compiler (claims → obligations).**
Deterministic pass: walks each derivation chain, intersects license scopes across ingredients, resolves conflicts conservatively (narrowest-scope-wins), emits an effective-permission set per asset: `{publish: {channels:[social], territories:[US], until: 2027-03}, remix: false, train_on: false, ...}`. This is where the old PBAC algebra finally gets a real dataset: content chains instead of database tuples.

**3. Enforcement Point (the agent-side gate).**
Wraps the production agent's action space. Every side-effectful action — export, upload, paid regeneration, license grant to a distributor — is checked against the target asset's compiled permission set *before* execution. Check is local, deterministic, milliseconds. On deny, the gate returns *which* claim failed ("music bed licensed for festival use only; trailer distribution not covered"), turning compliance from a wall into a worklist.

**4. Negotiation Loop (the novel loop).**
When an action lacks coverage, a second agent drafts the missing instrument — a scoped license request, a likeness re-consent for new territory, a buyout — grounded in the exact gap the compiler identified. Human countersigns; the signed claim enters the graph; recompile flips the decision. Autonomy grows out of documented rights, never around them.

The result no current system offers: **an AI production crew whose every public action is mechanically authorized by the cryptographic paper trail of everything it consumed — and an audit artifact (the full claim→decision chain) that E&O insurers and distributors can verify themselves.**

---

## 4. Why experts react

- **Distributed-systems / capability-security veterans:** it's capability-based security applied to content — unforgeable, attenuable, locally verifiable — with the twist that the *issuer's* inputs are themselves signed third-party claims. Delegation chains in macaroons have a visual cousin here: derivation chains.
- **PL/language people:** provenance-as-program with a conservative intersection semantics; conflict resolution as lattice meet; fail-closed evaluation gives the learned component (negotiation drafting) a soundness boundary — the LLM writes documents, the verifier admits them.
- **Entertainment attorneys / post supervisors:** this is their daily nightmare — "productions routinely arrive at post with unlicensed footage... because archival and clearance expertise is engaged too late" (25-year clearance veteran, currently building automation in this gap) [16]. Nothing existing computes clearance *continuously, during* creation.
- **Security people:** directly attacks the coming failure mode of agentic pipelines — agents shipping uncleared likenesses/music/training-derived material at machine speed. Also a clean answer to "how do you let agents touch copyrighted material without a lawyer in the loop?"

---

## 5. Novelty audit — searched and ruled out (with receipts)

Kill-searches run Aug 24, 2026: GitHub (c2pa-mcp, content-credentials repos — readers only), Hacker News via Algolia across six phrasings (zero relevant hits ever) [18], Product Hunt (rights SaaS only), web-wide product scans.

| Adjacent work | What it does | Why this is still new |
|---|---|---|
| **CopySight AI [29]** — closest competitor | $3M-seed "IP clearance layer for generative AI": frame-by-frame pixel analysis flags logos, resemblances, copyrightability risk in AI outputs; 87K checks since Jan 2026 | Inspects *pixels* statistically, after generation — a risk classifier with thresholds and false positives. This engine evaluates the *signed paper trail* deterministically, before action. Complementary layers, opposite mechanisms |
| ARCOS Labs / VN [30] | Fidelity-recognition engine measuring how much AI outputs reproduce protected characters/likenesses | Output-side measurement for rights holders; no permission derivation, no agent enforcement |
| KOR Protocol [31] | "AI-native clearinghouse": asset registration, licensing marketplace, royalty automation | Registry + deal flow + payments; nothing computes runtime permissions from provenance or gates agent actions |
| SAIL (Next Net × Sundial) [32] | Permissions/compensation framework for AI agents *consuming* publisher content ("rights-managed retrieval") | Ingestion-side governance; the production-side mirror (agents *creating* media) is untouched |
| TrueRights [13] — "the rights layer the ecosystem is missing" | Marketplace/pricing for likeness & content licenses; deal desks; monitoring | Human-negotiated instruments and dashboards. Doesn't read provenance chains, doesn't gate agent actions, no derived permission computation |
| Creation Rights [14] — "Media Production OS" with agent-oriented "MD files" | Company-owned context (metadata, rights, NILP®, approvals) exposed for tools/agents | Context *storage and handoff*. No claim that agents derive enforcement decisions from provenance; no compile-and-gate loop |
| 3PSync / Crux, ClearDraft, FADEL [15][16][17] | Third-party asset tracking; AI-assisted legal clearance with lawyer review; enterprise rights mgmt | Human-workflow automation for traditional assets; no cryptographic provenance ingestion; no agent enforcement point |
| C2PA Viewer MCP + official c2pa-mcp [3] | Agents can *read* manifests, get plain-language verdicts | Read-only reporting; zero decision semantics; no license layer at all |
| MCP #3225 `org.c2pa/credential` [2] | Standard slot for carrying credentials in MCP traffic | Transport convention only — explicitly attests nothing, enforces nothing |
| Multi-agent copyright framework (2601.06232) [7] | Director/Generator/Reviewer/Protection agents; embeds watermarks | Writes provenance onto outputs; never reads it back into authorization |
| AgentODRL (2512.00602) [8] | LLM agents author ODRL policies from natural language | Authoring from prose; no provenance source, no enforcement integration |
| VIGIL (2606.26524), policy-guard compilation (2507.16459) [9][10] | Runtime enforcement of *authored* behavioral specs over agent actions | Policies originate in skill specs/operator rules/company docs — never in signed asset provenance |
| Prov-PBAC lineage, IPBAC (2602.07722) [11] | Access control keyed on data/system provenance | Database-tuple and interaction-log provenance; predates C2PA; no generative-media or licensing semantics |
| EKILA (2304.04639) [12] | NFT-era attribution + training-consent tokens for generative art | Consent-for-*training* economics; not runtime action gating for production pipelines |

Also examined and rejected as cores: deepfake detection SaaS (classifies pixels, ignores paperwork); DRM (encrypts delivery channels, orthogonal to clearance decisions); blockchain rights registries (record-keeping, no agent enforcement); Google's SynthID Detector (answers "was this made by Google AI", not "may this be used").

**Closest single work:** Creation Rights' agent-context pitch — same instinct that agents need rights context, but it delivers context files rather than derived, enforceable decisions. Second closest: VIGIL — same enforcement architecture, but starved of provenance-born policy.

---

## 6. Market & competitor analysis (second pass, Aug 24 2026)

**Market size and shape.**
- Generative AI in media & entertainment: **$2.2–5.0B (2025)** growing at **25–40% CAGR** across major analyst houses ($2.24B→$21.2B by 2035 per Precedence [21]; $4.95B→$69.0B by 2033 per Grand View [22]; $2.5B→$8.06B by 2030 per TBRC [23]). By end-user, **film & TV studios are the largest segment (21.3%)** and film/TV production the fastest-growing application; advertising/marketing content is #1 by spend [21].
- The clearance-relevant wedge inside that: every dollar of AI-generated media spend is creating liability nobody can currently underwrite (below). This is a picks-and-shovels slice of a steep growth curve — infrastructure taxed on volume of AI content *produced*, not on creative quality.

**The fear budget — why buyers will pay (three independent money pumps):**
1. **Litigation:** Disney, Universal + 5 affiliates v. Midjourney (June 2025, consolidated with Warner Bros.) seeks statutory damages up to **$150,000 per work** ($20M+ on the listed works alone) and — critically — an injunction requiring Midjourney to adopt "tech that can prevent and flag" infringing generation [24]. Studios are simultaneously plaintiffs against AI and eager AI adopters: they need exactly this machinery to use it safely.
2. **Insurance:** On **Jan 1, 2026 Verisk published standardized endorsement forms (CG 40 47 / CG 40 48) letting carriers exclude generative-AI losses from commercial policies** [25]. AI-heavy producers face losing E&O coverage entirely — and distributors require $1M/$3M–$5M E&O before touching any production [26]. Provable provenance+clearance is becoming an insurability precondition; specialty "generative-AI liability" products are appearing to fill the gap [25]. An auditable claim→decision trail is literally premium-reducing collateral.
3. **Legal labor:** Entertainment counsel bills $350–950+/hr in California [27]; documentary clearance review starts ~$2,500 with multi-week turnarounds [28]; music rights for a single doc can rival production cost, popular songs $25K+ each, and uncleared music renders finished films unreleasable [33]. Human clearance doesn't scale into pipelines generating thousands of assets/day.

**Competitor map (validated money, none do this):**

| Company | Money behind it | What they actually sell | Overlap |
|---|---|---|---|
| CopySight AI | $3M seed (Mucker), AGBO/ArentFox/OpenArt clients, 87K checks since Jan 2026 [29] | Pixel-level IP risk detection on AI outputs | Closest. Still output-side classification vs. provenance-derived enforcement |
| ARCOS Labs (VN) | Serial founder w/ $50M track record, launched Aug 18 2026 [30] | Fidelity measurement of outputs vs. protected works | Rights-holder analytics, not pipeline gating |
| KOR Protocol | $7.5M Series A @ $100M valuation, Jul 2026; Black Mirror/Banijay partners [31] | Licensing clearinghouse/marketplace + royalties | Deal flow, not runtime permission derivation |
| SAIL (Next Net × Sundial) | Corporate-backed standard initiative, Jul 2026 [32] | Agent-consumption licensing framework ("rights-managed retrieval") | Ingestion-side; production-side mirror untouched |
| Loti ($22M) / Vermillio ($16M, Sony) | WME partnership, agency clients [34] | Likeness deepfake detection + takedowns | Enforcement after harm; no prevention layer |
| Rightsline (+FilmTrack+RSG) | Enterprise incumbent; Amazon Studios, BBC, Spotify, FIFA [35] | Contract/rights/royalties systems of record | Databases of human deals; no provenance ingestion, no agent gate |
| TrueRights / Creation Rights | Early-stage (2024–25 vintage) [13][14] | Rights marketplace / agent-context OS | Nearest conceptual neighbors; no derived-enforcement loop |

Read of the map: **~$50M+ of validated venture money entered adjacent layers within the last 14 months**, all converging on the same pain from different sides — but every one is either *detection* (pixels, post-hoc), *marketplaces* (deals between humans), or *registries*. Nobody sells **derived, deterministic authorization computed from signed provenance and enforced inside agent pipelines**. That window is open now; CopySight's existence proves budget exists, and its mechanism leaves the enforcement layer uncontested.

## 7b. Monetization — who pays, why it's obvious value

**Positioning line:** *"Compliance-as-code for AI media production."* Value is legible as classic risk math — expected loss × probability, versus subscription price:

**Pricing architecture (per-seat → per-volume hybrid):**
1. **Studio/platform tier:** enterprise license (Rightsline-class contracts run five figures/year per seat tier; price against one hour of outside counsel = $350–950). Anchor: "cost less than one cleared song."
2. **Per-check API:** usage-based pricing keyed to generation/publish volume — aligns revenue with the market's own CAGR curve. CopySight's 87K checks in ~7 months shows check volume is real and countable.
3. **Insurer/broker channel (the multiplier):** carriers writing generative-AI liability products need exactly this artifact to underwrite; bundled/discounted distribution turns the engine into the industry's inspection standard. This is how you get distribution without a sales force.

**Concrete buyer math:**
- Indie producer: replaces/augments $2.5K+ clearance counsel per project [28] and unblocks E&O binding (without which there is *no distribution deal at all* [26]) — payback on first project.
- Ad agency producing AI spots at volume: avoids per-asset legal review while gaining defensible audit trail; one avoided likeness settlement pays for years of usage fees.
- Studio platform team: the only mechanism that lets them adopt agentic production *at all* under the new insurance exclusions [25] — enables revenue (more AI production throughput) rather than just avoiding loss.
- Talent/likeness side: consent records become machine-checkable, so talent gets paid when agents use their face — new revenue for creators, reduced exposure for producers (Loti/Vermillio prove willingness-to-pay on this emotion).

**Why value is *clearly seen*: it converts an uninsurable/unauditable process into a priced artifact.** The demo shows a blocked action with a named missing claim and a one-click path to fix it — judges and buyers both immediately get "this saves me a lawyer loop per asset and keeps my coverage."

---

## 8. Fit to Agentic Cinema (and why it beats "another film crew")

The brief asks for agents solving "critical bottlenecks across the entertainment and media value chain" for filmmakers/studios [1], judged on Technological Implementation (Google Cloud + partner services), Design, Potential Impact, Quality of the Idea. Everyone else will demo multi-agent filmmaking pipelines — EditDuet-style editor/critic systems and Veo orchestration are already published and expected. This is the **non-obvious infrastructure play underneath any of them**, which is precisely what "creative, non-obvious use" rewards:

- **Google Cloud/Gemini:** Veo/Imagen generations arrive with C2PA+SynthID by default — native raw material; Cloud AI Content Detection API is the verification oracle; Gemini compiles/negotiates; Cloud IAM mirrors the gate pattern.
- **Partner tracks (pick one):**
  - **ClickHouse (recommended):** the Rights Graph *is* an analytics problem at studio scale — millions of assets, deep derivation chains, real-time permission lookups during generation loops; the managed ClickHouse MCP server [19] + columnar joins = the clearance lookup engine. Clean, deep, defensible integration.
  - **Parallel:** the Negotiation Loop's market leg — FindAll/Task APIs to locate and research rights holders and comparable-license benchmarks via its MCP servers [20], Extract for contract terms. Strong secondary.
  - **Grafana:** continuous compliance monitoring/alerting over clearance state (expiring windows, expired consents still in active cuts). Good dashboard story, thinner core.
- **Hackathon-feasible (48h):** c2patool signs/reads manifests today (open-source SDK); ODRL is just JSON; the compiler is a few hundred lines of conservative set-intersection; the gate is a tool-wrapper; the demo needs no real money — a scripted mini-studio: generate shot with Veo → attach mock likeness consent → composite with a music bed whose manifest says festival-only → agent tries to publish a trailer → **blocked with reason** → negotiation agent drafts the extension → human approves → publish sails through. That single arc demonstrates the entire thesis.

---

## 9. Honest limitations (say these before the judges do)

- **Competitive clock is ticking:** CopySight raised its seed months ago and ARCOS/KOR/SAIL all launched within weeks of this writing [29][30][31][32] — the layer is being contested *now*. The defense is positioning (they detect pixels; this enforces credentials), speed, and the fact that detection and enforcement are complementary — but a well-funded pivot into derived permissions is plausible within a year.

- **The garbage-in problem:** C2PA proves a chain is intact, not that its claims are true; a formal-methods analysis (Apr 2026) argues current C2PA falls short even of its own stated security goals [6]. The engine's guarantees are conditional on claim issuers being honest — which is exactly why fail-closed defaults, trust-listed signers, and the audit trail matter. Name this; don't hide it.
- **Coverage gaps:** Midjourney, Flux, most ComfyUI/local workflows ship *no* C2PA manifests today [5]; unsigned ingredients must default to blocked-or-quarantined, which will feel aggressive until coverage matures.
- **License semantics are gnarly:** fair use, territory edge cases, and renewal chains resist clean set-intersection; v1 handles explicit-machine-readable terms only and punts the rest to humans — that punt is a feature (fail-closed), but expect "this is just ODRL evaluation" pushback; the answer is *no one has sourced ODRL evaluation from cryptographic provenance chains inside an agent loop*.
- **Could it exist somewhere unseen?** Studio internal tooling is famously closed (Adobe/BBC Research contributions to C2PA hint at internal appetite), and one stealth-stage company could exist below search radar — though nothing in patents-visible space, Product Hunt, HN, or the startup press (TrueRights/Creation Rights both founded 2024–25, both marketing this exact void as their wedge) suggests it does. Academic sweep of cs.CR/cs.AI/cs.PL 2024–26 found the two nearest neighbors (VIGIL, AgentODRL) each missing the other's half.
- **Scope discipline risk:** the full vision (marketplaces, payment rails, insurer integrations) is a company, not a hackathon project. The narrow wedge — derive → gate → explain → negotiate-one-gap — is the 48-hour build.

## Sources

[1] https://web.archive.org/web/20260720232644/https://agentic-cinema.devpost.com/ — Agentic Cinema brief + judging criteria (archived Jul 20, 2026)
[2] https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/3225 — Standardizing org.c2pa/credential in MCP
[3] https://c2paviewer.com/articles/how-to-verify-c2pa-content — Verification semantics ("integrity, not truth"); C2PA Viewer MCP; official c2pa-mcp
[4] https://news.creeta.com/en/synthid-c2pa-ai-media-provenance-2026 — SynthID+C2PA dual-layer baseline; Gemini Enterprise detection API
[5] https://changegamer.ai/resources/c2pa-content-credentials — Who ships C2PA today; what doesn't
[6] https://arxiv.org/abs/2604.24890 — Verifying Provenance of Digital Media: Why C2PA Falls Short (Apr 2026)
[7] https://arxiv.org/abs/2601.06232 — Multi-Agent Framework for Controllable and Protected Generative Content Creation (Jan 2026)
[8] https://arxiv.org/abs/2512.00602 — AgentODRL: LLM-based Multi-agent System for ODRL Generation (Nov 2025)
[9] https://arxiv.org/abs/2507.16459 — Towards Enforcing Company Policy Adherence in Agentic Workflows (Jul 2025)
[10] https://arxiv.org/abs/2606.26524 — VIGIL: Runtime Enforcement of Behavioral Specifications in AI Agent Skills (Jun 2026)
[11] https://arxiv.org/abs/2602.07722 — IPBAC: Interaction Provenance-Based Access Control (Feb 2026); Prov-PBAC lineage 2010–2014
[12] https://arxiv.org/abs/2304.04639 — EKILA: Synthetic Media Provenance and Attribution for Generative Art (2023)
[13] https://truerights.com — TrueRights: "the rights layer the ecosystem is currently missing"
[14] https://creationrights.com — Creation Rights: Media Production OS, agent context files, NILP® clearance
[15] https://cleardraft.com — ClearDraft: AI-assisted legal clearance with lawyer review
[16] https://linkedin.com/in/teddy-cannon — Crux Entertainment / 3PSync: clearance automation, practitioner gap statement
[17] https://fadel.com/resources/who-owns-ai-generated-content-the-truth-about-rights-and-licensing — FADEL: layered AI licensing complexity
[18] https://hn.algolia.com/api/v1/search?query=content%20credentials%20license%20enforcement — HN Algolia API searches (six phrasings incl. "C2PA rights clearance", "AI film chain of title software") returned zero relevant hits, Aug 24 2026
[19] https://clickhouse.com/blog/clickhouse-agents-beta — ClickHouse Agents + managed MCP server
[20] https://docs.parallel.ai/integrations/mcp/quickstart — Parallel Search/Task MCP servers
[21] https://www.precedenceresearch.com/generative-ai-in-the-media-and-entertainment-market — GenAI in M&E: $2.24B (2025) → $21.2B (2035), 25.2% CAGR; film/TV studios 21.3% of market
[22] https://www.grandviewresearch.com/horizon/statistics/generative-ai-market/end-use/media-entertainment/global — Grand View: $4.95B (2025) → $69.0B (2033), 39.9% CAGR
[23] https://www.thebusinessresearchcompany.com/report/generative-ai-in-media-and-entertainment-global-market-report — TBRC: $2.5B (2025) → $8.06B (2030), 26.4% CAGR
[24] https://legalclarity.org/midjourney-lawsuit-claims-defenses-and-current-case-status — Disney/Universal/Warner v. Midjourney: $150K/work statutory damages, injunction seeking generation-blocking tech
[25] https://www.axisaistudios.com/blog/how-ai-native-production-changes-insurance-and-e-o-requirements — Verisk CG 40 47/48 GenAI exclusion endorsements (Jan 1 2026); GenAI liability insurance products
[26] https://kellyinsurancegroup.com/film-e-and-o-faq — Distributor-required E&O limits ($1M/$3M–$5M)
[27] https://www.lawlinq.com/how-much-does-it-cost-to-hire-an-entertainment-lawyer-california/ — CA entertainment counsel rates $350–950+/hr
[28] https://amyemitchell.com/services/documentary-clearance-counsel/ — Clearance counsel from $2,500; fair-use E&O opinion letters $1,500+
[29] https://linkedin.com/company/copysight — CopySight AI: $3M seed, "IP clearance layer for generative AI", 87K checks since Jan 2026
[30] https://www.prnewswire.com/news-releases/arcos-labs-launches-to-protect-human-creativity-in-the-age-of-ai-unveils-nelson-chu-as-founder-and-ceo-302854118.html — ARCOS Labs launch (Aug 18 2026), VN fidelity engine
[31] https://lucidityinsights.com/news/kor-protocol-raises-us75m-series-a — KOR Protocol: $7.5M Series A, AI-native licensing clearinghouse
[32] https://briefglance.com/articles/a-new-compass-for-ai-can-sail-end-the-content-copyright-wars — SAIL (Next Net × Sundial): agent-content permission framework
[33] https://www.documentary.org/feature/music-rights-clearance-what-you-dont-know-can-hurt-you — Music clearance economics: $500 minimums, $25K+ songs, unreleasable films
[34] https://www.geekwire.com/2025/seattle-startup-loti-lands-16m-to-help-celebs-politicians-and-ceos-detect-deepfakes — Loti $16.2M round / $22M total; Vermillio $16M; WME partnerships
[35] https://openrights.blog/reviews/2026 — Rightsline rollup (FilmTrack Jun 2024, RSG Sep 2024); rights-management vendor landscape
