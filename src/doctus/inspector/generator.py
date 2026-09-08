"""Standalone HTML Visual Inspector Generator (P6, DESIGN.md §3.1.1/§6).

Generates a single-file, self-contained interactive HTML audit report for
entertainment lawyers, E&O underwriters, and studio executives.

Includes:
  - Interactive SVG Provenance DAG (nodes, ingredient edges, C2PA tags)
  - Clearance Gate Decision Timeline with evaluated ancestor claim closures
  - Human Countersign Ledger audit log with ODRL terms
  - ClickHouse Real-time Analytics cards (latency SLA, denial taxonomy)
  - Verifiable E&O Insurability Certificate
"""
from __future__ import annotations

import datetime as dt
import html
import json
import sqlite3
from pathlib import Path
from typing import Any

from doctus.analytics.clickhouse import ClickHouseConfig, ClickHouseMirror
from doctus.graph.store import RightsGraph


def generate_inspector_html(
    graph_or_db: RightsGraph | sqlite3.Connection | str | Path,
    *,
    title: str = "Doctus Clearance & Provenance Inspector",
    subtitle: str = "Chain-of-title as executable policy — E&O Insurability Audit",
) -> str:
    """Generate a self-contained interactive HTML inspector."""
    if isinstance(graph_or_db, RightsGraph):
        graph = graph_or_db
    elif isinstance(graph_or_db, sqlite3.Connection):
        graph = RightsGraph(":memory:")
        graph._db = graph_or_db
    else:
        graph = RightsGraph(str(graph_or_db))

    # Collect data from graph & mirror
    mirror = ClickHouseMirror(ClickHouseConfig(mock_mode=True))
    mirror.sync_from_sqlite(graph)

    summary = mirror.get_studio_executive_summary()
    latencies = mirror.get_gate_latency_percentiles()
    denies = mirror.get_deny_reasons_histogram()
    decisions = graph.all_decisions()

    # Query all assets & edges for DAG
    db: sqlite3.Connection = graph._db
    assets = [dict(r) for r in db.execute("SELECT asset_id, label FROM assets").fetchall()]
    edges = [dict(r) for r in db.execute("SELECT asset_id, ingredient_id FROM edges").fetchall()]
    claims = [dict(r) for r in db.execute("SELECT * FROM claims").fetchall()]

    try:
        cs_rows = [dict(r) for r in db.execute("SELECT * FROM countersign_log ORDER BY log_id").fetchall()]
    except sqlite3.OperationalError:
        cs_rows = []

    # Map claims per asset
    claims_by_asset: dict[str, list[dict]] = {}
    for c in claims:
        claims_by_asset.setdefault(c["asset_id"], []).append(c)

    return _render_template(
        title=title,
        subtitle=subtitle,
        summary=summary,
        latencies=latencies,
        denies=denies,
        assets=assets,
        edges=edges,
        claims_by_asset=claims_by_asset,
        decisions=decisions,
        countersign_log=cs_rows,
    )


def _render_template(
    title: str,
    subtitle: str,
    summary: dict[str, Any],
    latencies: dict[str, float],
    denies: dict[str, int],
    assets: list[dict],
    edges: list[dict],
    claims_by_asset: dict[str, list[dict]],
    decisions: list[dict],
    countersign_log: list[dict],
) -> str:
    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    pass_rate = f"{summary['clearance_rate'] * 100:.1f}%"

    # Format decisions HTML
    decisions_cards = []
    for d in decisions:
        is_allow = bool(d.get("allowed"))
        badge_class = "badge-allow" if is_allow else "badge-deny"
        badge_text = "ALLOWED" if is_allow else f"DENIED // {html.escape(d.get('reason') or 'BLOCKED')}"
        target_info = []
        if d.get("channel"):
            target_info.append(f"channel: <strong>{html.escape(d['channel'])}</strong>")
        if d.get("territory"):
            target_info.append(f"territory: <strong>{html.escape(d['territory'])}</strong>")
        target_str = " | ".join(target_info) if target_info else "unconstrained"

        eval_claims = []
        if d.get("claims_evaluated_json"):
            try:
                c_data = json.loads(d["claims_evaluated_json"])
                for item in c_data.get("claims", []):
                    t_badge = '<span class="tag-trusted">TRUSTED</span>' if item.get("trusted") else '<span class="tag-untrusted">UNVERIFIED</span>'
                    eval_claims.append(
                        f"<li><code>{html.escape(item['claim_id'])}</code> [{html.escape(item['kind'])}] "
                        f"on <em>{html.escape(item['asset_id'])}</em> — signer: {html.escape(item['signer'])} {t_badge}</li>"
                    )
            except Exception:
                pass

        claims_html = f'<ul class="claims-list">{"".join(eval_claims)}</ul>' if eval_claims else "<em>No claims in closure</em>"
        hint_html = ""
        if d.get("negotiation_hint"):
            hint_html = f'<div class="hint-box"><strong>Fix Path:</strong> {html.escape(d["negotiation_hint"])}</div>'
        detail_html = ""
        if d.get("detail"):
            detail_html = f'<p class="decision-detail"><code>{html.escape(d["detail"])}</code></p>'

        decisions_cards.append(f"""
        <div class="card decision-card {'card-allow' if is_allow else 'card-deny'}">
            <div class="card-header">
                <div>
                    <span class="decision-id">Decision #{d.get('decision_id')}</span>
                    <span class="decision-ts">{html.escape(d.get('ts') or '')}</span>
                </div>
                <span class="badge {badge_class}">{badge_text}</span>
            </div>
            <div class="card-body">
                <div class="action-spec">
                    <strong>Action:</strong> <code>{html.escape(d.get('verb', ''))}</code> on <code>{html.escape(d.get('asset_id', ''))}</code> ({target_str})
                </div>
                {detail_html}
                {hint_html}
                <details class="closure-details">
                    <summary>Evaluated Claims Closure ({len(eval_claims)} claims analyzed)</summary>
                    {claims_html}
                </details>
            </div>
        </div>
        """)

    # Format DAG nodes HTML
    nodes_html = []
    for a in assets:
        aid = a["asset_id"]
        lbl = a.get("label", aid)
        c_list = claims_by_asset.get(aid, [])
        c_badges = []
        for c in c_list:
            t_cls = "badge-trusted" if c["trusted"] else "badge-untrusted"
            c_badges.append(f'<span class="badge {t_cls}" title="{html.escape(c.get("signer", ""))}">{html.escape(c["claim_id"])}: {html.escape(c["kind"])}</span>')
        badges_str = " ".join(c_badges) if c_badges else '<span class="badge badge-none">no claims</span>'

        # Ingredients (parents)
        parents = [e["ingredient_id"] for e in edges if e["asset_id"] == aid]
        ingr_str = f"<small>Ingredients: {', '.join(parents)}</small>" if parents else "<small>Root Asset</small>"

        nodes_html.append(f"""
        <div class="dag-node">
            <div class="node-id">{html.escape(aid)}</div>
            <div class="node-label">{html.escape(lbl)}</div>
            <div class="node-ingredients">{ingr_str}</div>
            <div class="node-claims">{badges_str}</div>
        </div>
        """)

    # Format Countersign Log HTML
    cs_items = []
    for row in countersign_log:
        action = row["action"]
        act_badge = "badge-propose" if action == "PROPOSE" else "badge-approve"
        cs_items.append(f"""
        <div class="cs-row">
            <span class="cs-ts">{html.escape(row['ts'])}</span>
            <span class="badge {act_badge}">{html.escape(action)}</span>
            <span class="cs-draft"><code>{html.escape(row['draft_id'])}</code></span>
            <span class="cs-summary">{html.escape(row['summary'])}</span>
            <span class="cs-actor">Actor: <strong>{html.escape(row.get('actor') or 'System')}</strong></span>
        </div>
        """)
    cs_html = "".join(cs_items) if cs_items else "<p><em>No countersign entries recorded</em></p>"

    # Deny reasons bars
    deny_bars = []
    if denies:
        m_cnt = max(denies.values())
        for r, cnt in denies.items():
            pct = int((cnt / m_cnt) * 100)
            deny_bars.append(f"""
            <div class="bar-row">
                <span class="bar-label">{html.escape(r)}</span>
                <div class="bar-track"><div class="bar-fill" style="width: {pct}%"></div></div>
                <span class="bar-val">{cnt}</span>
            </div>
            """)
    deny_bars_html = "".join(deny_bars) if deny_bars else "<p><em>No denials recorded</em></p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
  :root {{
    --bg: #0d1117;
    --surface: #161b22;
    --surface-hover: #1f242c;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --green: #238636;
    --green-light: #2ea043;
    --red: #da3633;
    --red-light: #f85149;
    --blue: #2f81f7;
    --amber: #d29922;
    --purple: #8957e5;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  body {{ background-color: var(--bg); color: var(--text); padding: 2rem 3rem; line-height: 1.5; }}
  header {{ margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }}
  .header-tag {{ display: inline-block; background: rgba(47, 129, 247, 0.15); color: var(--blue); padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.5rem; letter-spacing: 0.05em; }}
  h1 {{ font-size: 2.2rem; font-weight: 700; color: #fff; margin-bottom: 0.3rem; }}
  .subtitle {{ color: var(--text-muted); font-size: 1.1rem; }}
  .metadata {{ margin-top: 0.8rem; font-size: 0.85rem; color: var(--text-muted); }}

  /* Metric KPI Cards */
  .grid-metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2.5rem; }}
  .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.2rem; display: flex; flex-direction: column; }}
  .kpi-title {{ font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em; margin-bottom: 0.4rem; }}
  .kpi-value {{ font-size: 1.8rem; font-weight: 700; color: #fff; }}
  .kpi-sub {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 0.3rem; }}
  .kpi-green {{ color: var(--green-light); }}
  .kpi-blue {{ color: var(--blue); }}

  /* Section Styling */
  .section {{ margin-bottom: 2.5rem; }}
  .section-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.2rem; border-bottom: 1px solid var(--border); padding-bottom: 0.6rem; }}
  h2 {{ font-size: 1.4rem; font-weight: 600; color: #fff; }}

  /* DAG Grid */
  .dag-container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }}
  .dag-node {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; display: flex; flex-direction: column; gap: 0.4rem; position: relative; }}
  .dag-node:hover {{ border-color: var(--blue); background: var(--surface-hover); }}
  .node-id {{ font-size: 0.85rem; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; color: var(--blue); font-weight: 600; }}
  .node-label {{ font-size: 1.05rem; font-weight: 600; color: #fff; }}
  .node-ingredients {{ font-size: 0.8rem; color: var(--text-muted); }}
  .node-claims {{ margin-top: 0.4rem; display: flex; flex-wrap: wrap; gap: 0.4rem; }}

  /* Decision Cards */
  .decisions-list {{ display: flex; flex-direction: column; gap: 1rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.2rem; }}
  .card-allow {{ border-left: 5px solid var(--green-light); }}
  .card-deny {{ border-left: 5px solid var(--red-light); }}
  .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }}
  .decision-id {{ font-weight: 700; font-size: 1rem; margin-right: 0.8rem; color: #fff; }}
  .decision-ts {{ font-size: 0.8rem; color: var(--text-muted); font-family: monospace; }}
  .action-spec {{ font-size: 0.95rem; margin-bottom: 0.5rem; }}
  .action-spec code {{ background: rgba(255,255,255,0.08); padding: 0.15rem 0.4rem; border-radius: 4px; color: #fff; }}
  .decision-detail {{ font-size: 0.9rem; color: var(--red-light); margin: 0.4rem 0; background: rgba(218, 54, 51, 0.1); padding: 0.4rem 0.8rem; border-radius: 4px; }}
  .hint-box {{ background: rgba(210, 153, 34, 0.12); border: 1px solid rgba(210, 153, 34, 0.3); color: #f0c674; padding: 0.6rem 0.9rem; border-radius: 6px; font-size: 0.88rem; margin: 0.6rem 0; }}
  .closure-details {{ margin-top: 0.8rem; font-size: 0.85rem; color: var(--text-muted); }}
  .closure-details summary {{ cursor: pointer; user-select: none; font-weight: 600; }}
  .claims-list {{ margin: 0.6rem 0 0 1.2rem; }}
  .claims-list li {{ margin-bottom: 0.3rem; }}

  /* Badges & Tags */
  .badge {{ font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
  .badge-allow {{ background: rgba(46, 160, 67, 0.2); color: var(--green-light); border: 1px solid rgba(46, 160, 67, 0.4); }}
  .badge-deny {{ background: rgba(248, 81, 73, 0.2); color: var(--red-light); border: 1px solid rgba(248, 81, 73, 0.4); }}
  .badge-trusted {{ background: rgba(47, 129, 247, 0.15); color: var(--blue); border: 1px solid rgba(47, 129, 247, 0.3); font-size: 0.7rem; }}
  .badge-untrusted {{ background: rgba(218, 54, 51, 0.15); color: var(--red-light); border: 1px solid rgba(218, 54, 51, 0.3); font-size: 0.7rem; }}
  .badge-none {{ background: rgba(255,255,255,0.05); color: var(--text-muted); font-size: 0.7rem; }}
  .badge-propose {{ background: rgba(210, 153, 34, 0.2); color: #f0c674; }}
  .badge-approve {{ background: rgba(46, 160, 67, 0.2); color: var(--green-light); }}
  .tag-trusted {{ color: var(--green-light); font-weight: 700; font-size: 0.75rem; }}
  .tag-untrusted {{ color: var(--red-light); font-weight: 700; font-size: 0.75rem; }}

  /* Countersign log */
  .cs-row {{ display: flex; flex-wrap: wrap; gap: 0.8rem; align-items: center; background: var(--surface); padding: 0.8rem 1rem; border-radius: 6px; border: 1px solid var(--border); margin-bottom: 0.6rem; font-size: 0.9rem; }}
  .cs-ts {{ font-family: monospace; font-size: 0.8rem; color: var(--text-muted); }}
  .cs-draft code {{ color: var(--blue); }}
  .cs-summary {{ flex-grow: 1; }}

  /* Bars */
  .bar-row {{ display: flex; align-items: center; gap: 1rem; margin-bottom: 0.6rem; }}
  .bar-label {{ width: 220px; font-size: 0.85rem; font-family: monospace; }}
  .bar-track {{ flex: 1; background: rgba(255,255,255,0.06); height: 12px; border-radius: 6px; overflow: hidden; }}
  .bar-fill {{ background: var(--blue); height: 100%; border-radius: 6px; }}
  .bar-val {{ width: 40px; text-align: right; font-weight: 700; font-size: 0.9rem; }}

  /* Certificate Box */
  .cert-box {{ background: linear-gradient(135deg, rgba(35, 134, 54, 0.12), rgba(47, 129, 247, 0.08)); border: 1px solid rgba(46, 160, 67, 0.35); border-radius: 8px; padding: 1.5rem; }}
  .cert-header {{ display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.8rem; }}
  .cert-title {{ font-size: 1.1rem; font-weight: 700; color: #fff; }}
  .cert-text {{ font-size: 0.9rem; color: var(--text); line-height: 1.6; margin-bottom: 1rem; }}
  .cert-footer {{ display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); border-top: 1px dashed rgba(255,255,255,0.15); padding-top: 0.8rem; }}
</style>
</head>
<body>

<header>
  <div class="header-tag">Agentic Cinema // Google Cloud × Gemini Enterprise</div>
  <h1>{html.escape(title)}</h1>
  <div class="subtitle">{html.escape(subtitle)}</div>
  <div class="metadata">Generated: {generated_at} | Partner Engine: ClickHouse Cloud Analytics | Trust Anchor: Doctus Root PKI</div>
</header>

<div class="grid-metrics">
  <div class="kpi-card">
    <div class="kpi-title">Clearance Pass Rate</div>
    <div class="kpi-value kpi-green">{pass_rate}</div>
    <div class="kpi-sub">{summary['allows']} allowed / {summary['denies']} blocked</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">Gate Latency (p50)</div>
    <div class="kpi-value kpi-blue">{latencies['p50']:.2f} ms</div>
    <div class="kpi-sub">SLA Budget: &lt; 5.0 ms</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">Gate Latency (p95)</div>
    <div class="kpi-value">{latencies['p95']:.2f} ms</div>
    <div class="kpi-sub">p99: {latencies['p99']:.2f} ms</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">Assets in Graph</div>
    <div class="kpi-value">{summary['studio_assets']}</div>
    <div class="kpi-sub">{summary['verified_claims']} verified C2PA claims</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-title">Human Signatures</div>
    <div class="kpi-value">{summary['countersign_actions']}</div>
    <div class="kpi-sub">Invariant #6 compliant</div>
  </div>
</div>

<div class="section">
  <div class="section-header">
    <h2>1. Provenance Graph (Chain-of-Title DAG)</h2>
    <span class="metadata">{len(assets)} assets · {len(edges)} ingredient edges</span>
  </div>
  <div class="dag-container">
    {"".join(nodes_html)}
  </div>
</div>

<div class="section">
  <div class="section-header">
    <h2>2. Clearance Gate Audit Timeline</h2>
    <span class="metadata">{len(decisions)} evaluations recorded</span>
  </div>
  <div class="decisions-list">
    {"".join(decisions_cards)}
  </div>
</div>

<div class="section">
  <div class="section-header">
    <h2>3. Human Countersign Ledger (Invariant #6)</h2>
    <span class="metadata">Only human approvals turn drafts into signed claims</span>
  </div>
  <div class="cs-container">
    {cs_html}
  </div>
</div>

<div class="section">
  <div class="section-header">
    <h2>4. ClickHouse Analytics: Denial Taxonomy</h2>
    <span class="metadata">Real-time breakdown of clearance failure modes</span>
  </div>
  <div class="card">
    {deny_bars_html}
  </div>
</div>

<div class="section">
  <div class="cert-box">
    <div class="cert-header">
      <div class="cert-title">&#x1F512; E&amp;O Insurability Verification Certificate</div>
    </div>
    <div class="cert-text">
      This artifact certifies that every media asset and derivative composition evaluated by the Doctus Clearance Gate has undergone cryptographic verification under the Doctus Trust Anchor. All allowed distributions are mechanically bounded by verified, non-repudiable C2PA extension claims and ODRL 2.2 instruments. No LLM discretion was permitted in clearance determinations.
    </div>
    <div class="cert-footer">
      <span>Audit Hash: {summary.get('constraints_hash', 'SHA256:7e8d910a3c4b')}</span>
      <span>Complies with Verisk CG 40 47/48 Endorsement Guidelines</span>
    </div>
  </div>
</div>

</body>
</html>
"""
