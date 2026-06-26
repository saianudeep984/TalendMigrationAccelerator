"""
ExecutiveFlowLayout — Job 360 Executive Flowchart
A horizontal, phase-based executive visualization of a Talend job.
Standalone component. Not yet integrated into job_analysis_page.py.
"""

import re
import html as _html

import streamlit as st


# ── Phase definitions ──────────────────────────────────────────────────────────
EXECUTIVE_PHASES = [
    {"id": "source",          "label": "Source",          "icon": "🗄️"},
    {"id": "assessment",      "label": "Assessment",      "icon": "🔍"},
    {"id": "analysis",        "label": "Analysis",        "icon": "🧠"},
    {"id": "dependencies",    "label": "Dependencies",    "icon": "🔗"},
    {"id": "validation",      "label": "Validation",      "icon": "✅"},
    {"id": "readiness",       "label": "Readiness",       "icon": "📊"},
    {"id": "recommendations", "label": "Recommendations", "icon": "💡"},
]

# ── Color palette per phase ────────────────────────────────────────────────────
PHASE_COLORS = {
    "source":          {"bg": "#EFF6FF", "border": "#2563EB", "icon_bg": "#2563EB", "label": "#1D4ED8"},
    "assessment":      {"bg": "#F0FDF4", "border": "#16A34A", "icon_bg": "#16A34A", "label": "#15803D"},
    "analysis":        {"bg": "#FFF7ED", "border": "#EA580C", "icon_bg": "#EA580C", "label": "#C2410C"},
    "dependencies":    {"bg": "#F5F3FF", "border": "#7C3AED", "icon_bg": "#7C3AED", "label": "#6D28D9"},
    "validation":      {"bg": "#FFFBEB", "border": "#D97706", "icon_bg": "#D97706", "label": "#B45309"},
    "readiness":       {"bg": "#F0F9FF", "border": "#0284C7", "icon_bg": "#0284C7", "label": "#0369A1"},
    "recommendations": {"bg": "#FDF4FF", "border": "#9333EA", "icon_bg": "#9333EA", "label": "#7E22CE"},
}

_LAYOUT_CSS = """
<style>
/* ── Executive Flow Layout ── */
.efl-wrap {
    display: flex;
    align-items: stretch;
    gap: 0;
    width: 100%;
    overflow-x: hidden;
    padding: 12px 0 16px 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    box-sizing: border-box;
}
.efl-phase {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    position: relative;
}
.efl-connector {
    display: flex;
    align-items: flex-start;
    padding-top: 28px;
    flex-shrink: 0;
    width: 24px;
}
.efl-phase-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 10px 8px 8px;
    border-radius: 12px 12px 0 0;
    box-sizing: border-box;
}
.efl-phase-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    color: #fff;
}
.efl-phase-title {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.efl-phase-body {
    flex: 1;
    border-radius: 0 0 12px 12px;
    border-width: 0 1px 1px 1px;
    border-style: solid;
    padding: 8px 8px 10px;
    box-sizing: border-box;
    overflow: hidden;
}
.efl-empty-hint {
    font-size: 11px;
    color: #94A3B8;
    font-style: italic;
    text-align: center;
    padding: 8px 0;
}
</style>
"""


def _phase_html(phase: dict, cards_html: str = "") -> str:
    pid = phase["id"]
    colors = PHASE_COLORS[pid]
    icon = phase["icon"]
    label = phase["label"]
    body = cards_html if cards_html else f'<div class="efl-empty-hint">—</div>'
    return (
        f'<div class="efl-phase">'
        f'  <div class="efl-phase-header" style="background:{colors["bg"]};border:1px solid {colors["border"]};">'
        f'    <div class="efl-phase-icon" style="background:{colors["icon_bg"]};">{icon}</div>'
        f'    <div class="efl-phase-title" style="color:{colors["label"]};">{label}</div>'
        f'  </div>'
        f'  <div class="efl-phase-body" style="background:{colors["bg"]};border-color:{colors["border"]};">'
        f'    {body}'
        f'  </div>'
        f'</div>'
    )


def _connector_html() -> str:
    """Responsive SVG arrow between phases."""
    return (
        '<div class="efl-connector">'
        '<svg viewBox="0 0 28 16" xmlns="http://www.w3.org/2000/svg" '
        'width="28" height="16" style="display:block;">'
        '<line x1="2" y1="8" x2="22" y2="8" stroke="#CBD5E1" stroke-width="2" stroke-linecap="round"/>'
        '<polyline points="16,3 24,8 16,13" fill="none" stroke="#CBD5E1" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
        '</div>'
    )


def render_executive_flow_layout(phase_cards: dict | None = None) -> None:
    """
    Render the horizontal executive flow layout.

    Parameters
    ----------
    phase_cards : dict | None
        Optional dict keyed by phase id → HTML string of cards to inject.
        Example: {"source": "<div>...</div>", "assessment": "<div>...</div>"}
        If None or missing key, phase body renders as empty placeholder.
    """
    if phase_cards is None:
        phase_cards = {}

    html_parts = [_LAYOUT_CSS, '<div class="efl-wrap">']
    for i, phase in enumerate(EXECUTIVE_PHASES):
        if i > 0:
            html_parts.append(_connector_html())
        cards = phase_cards.get(phase["id"], "")
        html_parts.append(_phase_html(phase, cards))
    html_parts.append("</div>")

    st.markdown("".join(html_parts), unsafe_allow_html=True)


# ── Standalone preview (for dev testing only) ─────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Executive Flow Layout — Preview")
    from app.ui.design_system_v2 import std_page_header
    std_page_header("📊", "Executive Flow Layout", "P4 Static Preview")
    render_executive_flow_layout()


# ══════════════════════════════════════════════════════════════════════════════
# ExecutiveCard — P8/P9/P10/P11
# ══════════════════════════════════════════════════════════════════════════════

_CARD_CSS = """
<style>
.efc-card {
    background: #ffffff;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 8px 8px 8px;
    margin-bottom: 6px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    box-sizing: border-box;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    overflow: hidden;
}
.efc-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
}
.efc-card-icon {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
}
.efc-card-num {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #94A3B8;
    text-transform: uppercase;
    flex-shrink: 0;
}
.efc-card-title {
    font-size: 11px;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.3;
    flex: 1;
    word-break: break-word;
    overflow-wrap: break-word;
    min-width: 0;
}
.efc-card-desc {
    font-size: 10px;
    color: #64748B;
    line-height: 1.45;
    margin-top: 2px;
    word-break: break-word;
    overflow-wrap: break-word;
}
</style>
"""

# Phase color map for card icon backgrounds
_CARD_PHASE_COLORS = {
    "source":          ("#EFF6FF", "#2563EB"),
    "assessment":      ("#F0FDF4", "#16A34A"),
    "analysis":        ("#FFF7ED", "#EA580C"),
    "dependencies":    ("#F5F3FF", "#7C3AED"),
    "validation":      ("#FFFBEB", "#D97706"),
    "readiness":       ("#F0F9FF", "#0284C7"),
    "recommendations": ("#FDF4FF", "#9333EA"),
}


def executive_card_html(
    title: str,
    description: str,
    icon: str = "📌",
    number: int | None = None,
    phase_id: str = "source",
) -> str:
    """
    Return HTML string for a single ExecutiveCard.

    Parameters
    ----------
    title       : Card heading
    description : Supporting detail text
    icon        : Emoji icon
    number      : Optional sequence number (shown as prefix label)
    phase_id    : Controls icon background colour from PHASE_COLORS
    """
    bg, fg = _CARD_PHASE_COLORS.get(phase_id, ("#F8FAFC", "#334155"))
    num_html = (
        f'<span class="efc-card-num">#{number}</span>' if number is not None else ""
    )
    return (
        f'{_CARD_CSS}'
        f'<div class="efc-card">'
        f'  <div class="efc-card-header">'
        f'    <div class="efc-card-icon" style="background:{bg};color:{fg};">{icon}</div>'
        f'    {num_html}'
        f'    <div class="efc-card-title">{title}</div>'
        f'  </div>'
        f'  <div class="efc-card-desc">{description}</div>'
        f'</div>'
    )


def build_phase_cards_html(
    cards: list[dict],
    phase_id: str,
) -> str:
    """
    Build concatenated HTML for a list of card dicts.

    Each dict: {title, description, icon, number (optional)}
    """
    parts = []
    for i, c in enumerate(cards, start=1):
        parts.append(
            executive_card_html(
                title=c.get("title", "—"),
                description=c.get("description", ""),
                icon=c.get("icon", "📌"),
                number=c.get("number", i),
                phase_id=phase_id,
            )
        )
    return "".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# KeyInsightsPanel — P12/P13/P14
# ══════════════════════════════════════════════════════════════════════════════

_KIP_CSS = """
<style>
.kip-wrap {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    padding: 12px 0 4px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.kip-card {
    flex: 1;
    min-width: 110px;
    background: #ffffff;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 12px 14px;
    box-sizing: border-box;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.kip-card-icon {
    font-size: 20px;
    line-height: 1;
    margin-bottom: 4px;
}
.kip-card-value {
    font-size: 22px;
    font-weight: 800;
    line-height: 1;
}
.kip-card-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #64748B;
    margin-top: 2px;
}
.kip-card-sub {
    font-size: 11px;
    color: #94A3B8;
    margin-top: 1px;
}
.kip-title {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #94A3B8;
    margin-bottom: 2px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
</style>
"""

# Default metric definitions (static placeholders — overridden by bind in Phase 6)
_DEFAULT_METRICS = [
    {"icon": "⚙️", "label": "Complexity",    "value": "—",  "sub": "Pending analysis",  "color": "#0F172A"},
    {"icon": "🧩", "label": "Components",    "value": "—",  "sub": "Total in job",       "color": "#0F172A"},
    {"icon": "🔗", "label": "Dependencies",  "value": "—",  "sub": "Internal + external","color": "#0F172A"},
    {"icon": "📊", "label": "Readiness",     "value": "—",  "sub": "Cloud readiness",    "color": "#0F172A"},
]


def render_key_insights_panel(
    metrics: list[dict] | None = None,
    title: str = "Key Metrics",
) -> None:
    """
    Render compact executive metrics panel.

    Each metric dict: {icon, label, value, sub, color}
    Defaults to 4 placeholder cards if metrics is None.
    """
    if metrics is None:
        metrics = _DEFAULT_METRICS

    cards_html = ""
    for m in metrics:
        color = m.get("color", "#0F172A")
        cards_html += (
            f'<div class="kip-card">'
            f'  <div class="kip-card-icon">{m.get("icon","📌")}</div>'
            f'  <div class="kip-card-value" style="color:{color};">{m.get("value","—")}</div>'
            f'  <div class="kip-card-label">{m.get("label","")}</div>'
            f'  <div class="kip-card-sub">{m.get("sub","")}</div>'
            f'</div>'
        )

    st.markdown(
        f'{_KIP_CSS}'
        f'<div class="kip-title">{title}</div>'
        f'<div class="kip-wrap">{cards_html}</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# EndToEndExecutionFlow — P15/P16/P17/P18
# ══════════════════════════════════════════════════════════════════════════════

_E2E_CSS = """
<style>
.e2e-wrap {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    padding: 10px 0 6px;
}
.e2e-flow {
    display: flex;
    align-items: center;
    gap: 0;
    flex-wrap: nowrap;
    overflow-x: auto;
    padding: 8px 0 4px;
}
.e2e-box {
    flex-shrink: 0;
    min-width: 100px;
    max-width: 140px;
    background: #ffffff;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: center;
    box-sizing: border-box;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    border-width: 2px;
    border-style: solid;
}
.e2e-box-icon { font-size: 20px; margin-bottom: 4px; }
.e2e-box-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #0F172A;
    margin-bottom: 2px;
}
.e2e-box-sub {
    font-size: 10px;
    color: #64748B;
}
.e2e-arrow {
    flex-shrink: 0;
    padding: 0 2px;
    display: flex;
    align-items: center;
}
.e2e-legend {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid #E2E8F0;
}
.e2e-legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    color: #64748B;
    font-weight: 500;
}
.e2e-legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}
.e2e-title {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #94A3B8;
    margin-bottom: 4px;
}
</style>
"""

# Static node definitions — overridden by data binding in Phase 6
_E2E_DEFAULT_NODES = [
    {"label": "Source",   "sub": "Input system",    "icon": "🗄️",  "border": "#2563EB", "dot": "#2563EB"},
    {"label": "Input",    "sub": "Data ingestion",  "icon": "📥",  "border": "#16A34A", "dot": "#16A34A"},
    {"label": "Process",  "sub": "Transformation",  "icon": "⚙️",  "border": "#EA580C", "dot": "#EA580C"},
    {"label": "Output",   "sub": "Data emission",   "icon": "📤",  "border": "#D97706", "dot": "#D97706"},
    {"label": "Target",   "sub": "Destination",     "icon": "🎯",  "border": "#7C3AED", "dot": "#7C3AED"},
]

_E2E_SVG_ARROW = (
    '<svg viewBox="0 0 32 16" xmlns="http://www.w3.org/2000/svg" '
    'width="32" height="16" style="display:block;">'
    '<line x1="2" y1="8" x2="26" y2="8" stroke="#CBD5E1" stroke-width="2" stroke-linecap="round"/>'
    '<polyline points="19,3 27,8 19,13" fill="none" stroke="#CBD5E1" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    '</svg>'
)

_E2E_LEGEND_ITEMS = [
    {"color": "#2563EB", "label": "Source System"},
    {"color": "#16A34A", "label": "Input / Ingestion"},
    {"color": "#EA580C", "label": "Processing / Transform"},
    {"color": "#D97706", "label": "Output / Emit"},
    {"color": "#7C3AED", "label": "Target System"},
]


def render_end_to_end_flow(
    nodes: list[dict] | None = None,
    title: str = "End-to-End Execution Flow",
    show_legend: bool = True,
) -> None:
    """
    Render horizontal Source→Input→Process→Output→Target flow with SVG arrows.

    Each node dict: {label, sub, icon, border, dot}
    """
    if nodes is None:
        nodes = _E2E_DEFAULT_NODES

    # Build flow boxes + SVG arrows
    flow_html = '<div class="e2e-flow">'
    for i, node in enumerate(nodes):
        if i > 0:
            flow_html += f'<div class="e2e-arrow">{_E2E_SVG_ARROW}</div>'
        flow_html += (
            f'<div class="e2e-box" style="border-color:{node.get("border","#E2E8F0")};">'
            f'  <div class="e2e-box-icon">{node.get("icon","📌")}</div>'
            f'  <div class="e2e-box-label">{node.get("label","")}</div>'
            f'  <div class="e2e-box-sub">{node.get("sub","")}</div>'
            f'</div>'
        )
    flow_html += '</div>'

    # Build legend
    legend_html = ""
    if show_legend:
        legend_items = nodes  # use node dot colors
        legend_html = '<div class="e2e-legend">'
        for n in legend_items:
            legend_html += (
                f'<div class="e2e-legend-item">'
                f'  <div class="e2e-legend-dot" style="background:{n.get("dot", n.get("border","#CBD5E1"))};"></div>'
                f'  {n.get("label","")}'
                f'</div>'
            )
        legend_html += '</div>'

    st.markdown(
        f'{_E2E_CSS}'
        f'<div class="e2e-wrap">'
        f'  <div class="e2e-title">{title}</div>'
        f'  {flow_html}'
        f'  {legend_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Phase 6 — Data binding helpers (P19–P24)
# Converts Job360 dicts → phase_cards dicts ready for render_executive_flow_layout()
# ══════════════════════════════════════════════════════════════════════════════


def _card(title: str, description: str, icon: str, num: int, phase_id: str) -> str:
    return executive_card_html(title, description, icon, num, phase_id)


def bind_source_phase(inv: dict) -> str:
    """P19 — Source phase: source tables/files from inventory."""
    sources = inv.get("sources", [])
    if not sources:
        return '<div class="efl-empty-hint">No sources detected</div>'
    parts = []
    for i, s in enumerate(sources[:3], 1):
        raw_name = s.get("name", "Unknown")
        # Truncate long SQL names
        display_name = (raw_name[:32] + "…") if len(raw_name) > 32 else raw_name
        name = _html.escape(display_name)
        stype = _html.escape(s.get("type", ""))
        parts.append(_card(name, stype or "Source table / file", "🗄️", i, "source"))
    return "".join(parts)


def bind_assessment_phase(job: dict) -> str:
    """P19 — Assessment phase: complexity, risk level."""
    cx = job.get("complexity", {})
    level = cx.get("complexity", "—")
    score = cx.get("score", "—")
    risk_items = job.get("enterprise_risk_report", [])
    high_risk = sum(1 for r in risk_items if (r.get("risk") or "").upper() in ("HIGH", "CRITICAL"))
    parts = [
        _card("Complexity", f"Level: {level} (Score: {score})", "⚙️", 1, "assessment"),
        _card("Risk Items", f"{high_risk} High/Critical risk(s) found", "⚠️", 2, "assessment"),
    ]
    return "".join(parts)


def bind_analysis_phase(jd: dict) -> str:
    """P20 — Analysis phase: component count, SQL ops."""
    total_comps = len(jd.get("components", []))
    conns = len(jd.get("connections", []))
    parts = [
        _card("Components", f"{total_comps} component(s) in job graph", "🧩", 1, "analysis"),
        _card("Connections", f"{conns} connection(s) mapped", "🔀", 2, "analysis"),
    ]
    return "".join(parts)


def bind_dependency_phase(inv: dict, jd: dict) -> str:
    """P21 — Dependency phase: child jobs, routines."""
    child_jobs = [
        c for c in jd.get("components", [])
        if c.get("component_type", "") in ("tRunJob", "tPrejob", "tPostjob")
    ]
    routines = inv.get("routines", [])
    parts = [
        _card("Child Jobs", f"{len(child_jobs)} sub-job call(s)", "📂", 1, "dependencies"),
        _card("Routines", f"{len(routines)} routine reference(s)", "📚", 2, "dependencies"),
    ]
    return "".join(parts)


def bind_validation_phase(job: dict) -> str:
    """P22 — Validation phase: blockers, manual fixes."""
    blockers = job.get("blockers", [])
    manual_fixes = job.get("manual_fixes", [])
    parts = [
        _card("Blockers", f"{len(blockers)} migration blocker(s)", "🚫", 1, "validation"),
        _card("Manual Fixes", f"{len(manual_fixes)} items need review", "🔧", 2, "validation"),
    ]
    return "".join(parts)


def bind_readiness_phase(job: dict) -> str:
    """P23 — Readiness phase: cloud readiness RAG."""
    from app.analyzers.complexity_analyzer import EFFORT_HOURS
    cx = job.get("complexity", {})
    level = cx.get("complexity", "LOW")
    effort = EFFORT_HOURS.get("manual", 40) if level in ("HIGH", "CRITICAL") else EFFORT_HOURS.get("auto", 8)
    cloud = "Ready" if level not in ("HIGH", "CRITICAL") else "Needs Work"
    icon = "✅" if cloud == "Ready" else "🔶"
    parts = [
        _card("Cloud Readiness", cloud, icon, 1, "readiness"),
        _card("Est. Effort", f"{effort}h estimated migration effort", "⏱️", 2, "readiness"),
    ]
    return "".join(parts)


def bind_recommendations_phase(recs: list[dict]) -> str:
    """P24 — Recommendations phase: top auto-fix + manual items."""
    auto_fix = [r for r in recs if r.get("auto_fix")]
    manual = [r for r in recs if not r.get("auto_fix")]
    parts = [
        _card("Auto-Fix", f"{len(auto_fix)} recommendation(s) can be auto-fixed", "🤖", 1, "recommendations"),
        _card("Manual Review", f"{len(manual)} item(s) need manual attention", "👁️", 2, "recommendations"),
    ]
    return "".join(parts)


def build_all_phase_cards(
    job: dict,
    jd: dict,
    inv: dict,
    recs: list[dict],
) -> dict:
    """
    Convenience: build all phase_cards dict from Job360 data.
    Returns dict ready to pass into render_executive_flow_layout(phase_cards=...).
    """
    return {
        "source":          bind_source_phase(inv),
        "assessment":      bind_assessment_phase(job),
        "analysis":        bind_analysis_phase(jd),
        "dependencies":    bind_dependency_phase(inv, jd),
        "validation":      bind_validation_phase(job),
        "readiness":       bind_readiness_phase(job),
        "recommendations": bind_recommendations_phase(recs),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Phase 7 — Live metrics from Job360 data + RAG status (P25–P27)
# ══════════════════════════════════════════════════════════════════════════════

def _rag_color(value: str | int | float, thresholds: tuple = (33, 66)) -> str:
    """Return Red/Amber/Green hex based on numeric readiness or string level."""
    if isinstance(value, str):
        v = value.upper()
        if v in ("HIGH", "CRITICAL", "NOT READY", "RED"):
            return "#DC2626"
        if v in ("MEDIUM", "AMBER", "NEEDS WORK"):
            return "#D97706"
        return "#16A34A"
    lo, hi = thresholds
    if value < lo:
        return "#DC2626"
    if value < hi:
        return "#D97706"
    return "#16A34A"


def build_live_metrics(
    job: dict,
    jd: dict,
    inv: dict,
    recs: list[dict],
) -> list[dict]:
    """
    P25/P26/P27 — Build real KIP metrics from Job360 data with RAG color.

    Returns list of metric dicts for render_key_insights_panel().
    """
    from app.analyzers.complexity_analyzer import EFFORT_HOURS

    # Complexity
    cx = job.get("complexity", {})
    cx_level = cx.get("complexity", "LOW")
    cx_score = cx.get("score", 0)
    cx_color = _rag_color(cx_level)

    # Components
    total_comps = len(jd.get("components", []))
    comp_color = _rag_color(total_comps, thresholds=(5, 20))

    # Dependencies (child jobs + routines)
    child_jobs = sum(
        1 for c in jd.get("components", [])
        if c.get("component_type", "") in ("tRunJob", "tPrejob", "tPostjob")
    )
    routines = len(inv.get("routines", []))
    dep_total = child_jobs + routines
    dep_color = _rag_color(dep_total, thresholds=(2, 8))

    # Readiness
    effort = EFFORT_HOURS.get("manual", 40) if cx_level in ("HIGH", "CRITICAL") else EFFORT_HOURS.get("auto", 8)
    ready_label = "Ready" if cx_level not in ("HIGH", "CRITICAL") else "Not Ready"
    ready_color = _rag_color(ready_label)

    return [
        {
            "icon": "⚙️",
            "label": "Complexity",
            "value": cx_level,
            "sub": f"Score: {cx_score}",
            "color": cx_color,
        },
        {
            "icon": "🧩",
            "label": "Components",
            "value": str(total_comps),
            "sub": "In this job",
            "color": comp_color,
        },
        {
            "icon": "🔗",
            "label": "Dependencies",
            "value": str(dep_total),
            "sub": f"{child_jobs} sub-jobs · {routines} routines",
            "color": dep_color,
        },
        {
            "icon": "📊",
            "label": "Readiness",
            "value": ready_label,
            "sub": f"Est. {effort}h effort",
            "color": ready_color,
        },
    ]


def build_live_e2e_nodes(inv: dict, jd: dict) -> list[dict]:
    """
    Build EndToEndExecutionFlow nodes from real Job360 data.
    Returns list of node dicts for render_end_to_end_flow().
    """
    sources = inv.get("sources", [])
    targets = inv.get("targets", [])

    src_label = sources[0].get("name", "Source") if sources else "Source"
    tgt_label = targets[0].get("name", "Target") if targets else "Target"

    transform_types = {"tMap", "tJoin", "tSortRow", "tAggregateRow", "tNormalize", "tConvertType", "tReplace"}
    transforms = [c for c in jd.get("components", []) if c.get("component_type") in transform_types]
    proc_label = transforms[0].get("unique_name", "Process") if transforms else "Process"

    input_types = {"tFileInputDelimited", "tDBInput", "tFileInputExcel", "tFileInputJSON",
                   "tFileInputXML", "tFileInputPositional", "tHDFSInput", "tSalesforceInput"}
    inputs = [c for c in jd.get("components", []) if c.get("component_type") in input_types]
    inp_label = inputs[0].get("unique_name", "Input") if inputs else "Input"

    output_types = {"tFileOutputDelimited", "tDBOutput", "tFileOutputExcel", "tFileOutputJSON",
                    "tFileOutputXML", "tHDFSOutput", "tSalesforceOutput", "tLogRow"}
    outputs = [c for c in jd.get("components", []) if c.get("component_type") in output_types]
    out_label = outputs[0].get("unique_name", "Output") if outputs else "Output"

    return [
        {"label": _html.escape(src_label[:20]),  "sub": "Source system",      "icon": "🗄️", "border": "#2563EB", "dot": "#2563EB"},
        {"label": _html.escape(inp_label[:20]),  "sub": "Data ingestion",     "icon": "📥", "border": "#16A34A", "dot": "#16A34A"},
        {"label": _html.escape(proc_label[:20]), "sub": "Transformation",     "icon": "⚙️", "border": "#EA580C", "dot": "#EA580C"},
        {"label": _html.escape(out_label[:20]),  "sub": "Data emission",      "icon": "📤", "border": "#D97706", "dot": "#D97706"},
        {"label": _html.escape(tgt_label[:20]),  "sub": "Destination",        "icon": "🎯", "border": "#7C3AED", "dot": "#7C3AED"},
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Phase 8 — Export helpers (P28–P30)
# ══════════════════════════════════════════════════════════════════════════════

def executive_flow_to_html(
    phase_cards: dict,
    metrics: list[dict],
    e2e_nodes: list[dict],
    job_name: str = "Job",
) -> str:
    """
    P28/P29/P30 — Export full executive flow as standalone HTML.
    No clipping: all phases inline, no page breaks in card bodies.
    Single-page friendly.
    """
    phases_html = ""
    for i, phase in enumerate(EXECUTIVE_PHASES):
        colors = PHASE_COLORS[phase["id"]]
        if i > 0:
            phases_html += (
                '<div style="display:flex;align-items:center;padding-top:24px;flex-shrink:0;width:28px;">'
                '<svg viewBox="0 0 28 16" xmlns="http://www.w3.org/2000/svg" width="28" height="16">'
                '<line x1="2" y1="8" x2="22" y2="8" stroke="#CBD5E1" stroke-width="2" stroke-linecap="round"/>'
                '<polyline points="16,3 24,8 16,13" fill="none" stroke="#CBD5E1" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"/>'
                '</svg></div>'
            )
        body = phase_cards.get(phase["id"], "<em>—</em>")
        phases_html += (
            f'<div style="flex:1;min-width:120px;max-width:180px;display:flex;flex-direction:column;">'
            f'<div style="background:{colors["bg"]};border:1px solid {colors["border"]};border-radius:12px 12px 0 0;'
            f'display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px 10px 10px;">'
            f'<div style="width:40px;height:40px;border-radius:10px;background:{colors["icon_bg"]};'
            f'display:flex;align-items:center;justify-content:center;font-size:20px;">{phase["icon"]}</div>'
            f'<div style="font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;'
            f'color:{colors["label"]};">{phase["label"]}</div></div>'
            f'<div style="background:{colors["bg"]};border:0 1px 1px 1px solid {colors["border"]};'
            f'border-width:0 1px 1px 1px;border-style:solid;border-color:{colors["border"]};'
            f'border-radius:0 0 12px 12px;padding:10px 10px 12px;min-height:80px;">{body}</div>'
            f'</div>'
        )

    # Metrics strip
    metrics_html = ""
    for m in metrics:
        metrics_html += (
            f'<div style="flex:1;min-width:110px;background:#fff;border:1px solid #E2E8F0;border-radius:12px;'
            f'padding:12px 14px;box-shadow:0 1px 4px rgba(0,0,0,.05);">'
            f'<div style="font-size:20px;">{m.get("icon","")}</div>'
            f'<div style="font-size:22px;font-weight:800;color:{m.get("color","#0F172A")};">{m.get("value","—")}</div>'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#64748B;">'
            f'{m.get("label","")}</div>'
            f'<div style="font-size:11px;color:#94A3B8;">{m.get("sub","")}</div>'
            f'</div>'
        )

    # E2E flow
    e2e_html = ""
    for i, node in enumerate(e2e_nodes):
        if i > 0:
            e2e_html += (
                '<svg viewBox="0 0 32 16" xmlns="http://www.w3.org/2000/svg" width="32" height="16">'
                '<line x1="2" y1="8" x2="26" y2="8" stroke="#CBD5E1" stroke-width="2" stroke-linecap="round"/>'
                '<polyline points="19,3 27,8 19,13" fill="none" stroke="#CBD5E1" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"/></svg>'
            )
        e2e_html += (
            f'<div style="flex-shrink:0;min-width:100px;max-width:140px;background:#fff;border-radius:10px;'
            f'padding:10px 12px;text-align:center;border:2px solid {node.get("border","#E2E8F0")};">'
            f'<div style="font-size:20px;">{node.get("icon","")}</div>'
            f'<div style="font-size:11px;font-weight:700;color:#0F172A;">{node.get("label","")}</div>'
            f'<div style="font-size:10px;color:#64748B;">{node.get("sub","")}</div>'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Job 360 Executive Flow — {_html.escape(job_name)}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:#F4F6FB;color:#0F172A;padding:24px;}}
  h1{{font-size:18px;font-weight:800;margin-bottom:4px;}}
  .subtitle{{font-size:12px;color:#64748B;margin-bottom:20px;}}
  .section-label{{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#94A3B8;margin:16px 0 6px;}}
  .phases{{display:flex;align-items:flex-start;gap:0;overflow-x:auto;}}
  .metrics{{display:flex;gap:10px;flex-wrap:wrap;}}
  .e2e{{display:flex;align-items:center;gap:0;overflow-x:auto;flex-wrap:nowrap;}}
</style>
</head>
<body>
<h1>Job 360 Executive Flowchart</h1>
<div class="subtitle">{_html.escape(job_name)}</div>
<div class="section-label">Migration Phases</div>
<div class="phases">{phases_html}</div>
<div class="section-label">Key Metrics</div>
<div class="metrics">{metrics_html}</div>
<div class="section-label">End-to-End Execution Flow</div>
<div class="e2e">{e2e_html}</div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Phase 9 — Master render (P31–P35)
# Single-function entry point; all alignment, spacing, readability handled here
# ══════════════════════════════════════════════════════════════════════════════

def render_executive_job_360(
    job: dict,
    jd: dict,
    inv: dict,
    recs: list[dict],
    job_name: str = "Job",
    show_export: bool = True,
) -> None:
    """
    P35 — Final master render. Call from job_analysis_page.py.

    Renders:
      1. KeyInsightsPanel (live RAG metrics)
      2. ExecutiveFlowLayout (7 phases, data-bound)
      3. EndToEndExecutionFlow (source→target, data-bound)
      4. Optional HTML export button
    """
    import streamlit as st

    # ── 1. Live metrics ──────────────────────────────────────────────────────
    metrics = build_live_metrics(job, jd, inv, recs)
    render_key_insights_panel(metrics, title="Executive Metrics")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── 2. Phase flow ────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;'
        'color:#94A3B8;margin-bottom:4px;">Migration Phase Overview</div>',
        unsafe_allow_html=True,
    )
    phase_cards = build_all_phase_cards(job, jd, inv, recs)
    render_executive_flow_layout(phase_cards)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── 3. End-to-end flow ───────────────────────────────────────────────────
    e2e_nodes = build_live_e2e_nodes(inv, jd)
    render_end_to_end_flow(e2e_nodes, title="End-to-End Execution Flow")

    # ── 4. Export button ─────────────────────────────────────────────────────
    if show_export:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        html_out = executive_flow_to_html(phase_cards, metrics, e2e_nodes, job_name)
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", job_name)
        st.download_button(
            "📥 Export Executive Flow (HTML)",
            data=html_out,
            file_name=f"{safe}_executive_flow.html",
            mime="text/html",
            key=f"exec_flow_html_{safe}",
            width="content",
        )
