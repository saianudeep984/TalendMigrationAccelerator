"""
Overview Dashboard Page
=======================
Phase 2B — Overview Dashboard tab under the Home (Overview) section.

Displays repository-level metrics, scores, quick insights, and an AI summary
derived ENTIRELY from the existing Phase 1B / 1C cache.

No new parsing. No repository scans. No extra LLM calls.
All values are read from:
  - cache/phase_1b/analysis_cache.db      (Phase1BCache)
  - cache/phase_1c/lineage_cache.json     (lineage / dependency graph)
  - st.session_state                       (already-computed analysis results)
"""

from __future__ import annotations

import json
import os
import streamlit as st

# ── Cache paths (relative to app root) ───────────────────────────────────────
_PHASE1B_DB   = os.path.join("cache", "phase_1b", "analysis_cache.db")
_PHASE1C_JSON = os.path.join("cache", "phase_1c", "lineage_cache.json")


# ── Load helpers (cached in session to avoid re-reading on every rerun) ──────

def _load_repository_summary() -> dict:
    """Return the repository_summary dict from Phase 1B cache."""
    key = "_overview_repo_summary"
    if key not in st.session_state:
        try:
            from cache.phase_1b.load_from_cache import Phase1BCache
            cache = Phase1BCache(_PHASE1B_DB)
            st.session_state[key] = cache.get_repository_summary()
        except Exception:
            st.session_state[key] = {}
    return st.session_state[key]


def _load_migration_scores() -> list:
    """Return migration score dimensions from Phase 1B cache."""
    key = "_overview_migration_scores"
    if key not in st.session_state:
        try:
            from cache.phase_1b.load_from_cache import Phase1BCache
            cache = Phase1BCache(_PHASE1B_DB)
            st.session_state[key] = cache.get_migration_scores()
        except Exception:
            st.session_state[key] = []
    return st.session_state[key]


def _load_lineage_cache() -> dict:
    """Return the full Phase 1C lineage cache dict."""
    key = "_overview_lineage_cache"
    if key not in st.session_state:
        try:
            with open(_PHASE1C_JSON, encoding="utf-8") as f:
                st.session_state[key] = json.load(f)
        except Exception:
            st.session_state[key] = {}
    return st.session_state[key]


def _load_java_analysis() -> list:
    """Return java_analysis rows (all risks) from Phase 1B cache."""
    key = "_overview_java_analysis"
    if key not in st.session_state:
        try:
            from cache.phase_1b.load_from_cache import Phase1BCache
            cache = Phase1BCache(_PHASE1B_DB)
            st.session_state[key] = cache.get_java_analysis()
        except Exception:
            st.session_state[key] = []
    return st.session_state[key]


# ── Derived metric helpers ────────────────────────────────────────────────────

def _rag_color(rag: str) -> str:
    return {"GREEN": "#15803d", "AMBER": "#b45309", "RED": "#be123c"}.get(rag, "#475569")


# Canonical RAG conversion — all score→status mappings must use this.
# Thresholds: >=80 GREEN, >=60 AMBER, <60 RED.
from app.analyzers.health_score import rag_from_score as _score_to_rag, effort_from_complexity_distribution as _effort_from_dist


def _score_badge(score: int, rag: str | None = None) -> str:
    rag = rag or _score_to_rag(score)
    color = _rag_color(rag)
    bg = {"GREEN": "#eef7f2", "AMBER": "#fef8ee", "RED": "#fdf4f4"}.get(rag, "#f8fafc")
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}33;'
        f'border-radius:999px;padding:3px 10px;font-size:11px;font-weight:700;">'
        f'{score}/100 · {rag}</span>'
    )


def _effort_estimate(rs: dict) -> tuple[int, float]:
    """Return (total_hours, weeks) from complexity distribution — delegates to canonical engine."""
    result = _effort_from_dist(
        complexity_high=rs.get("complexity_high", 0),
        complexity_critical=rs.get("complexity_critical", 0),
        complexity_low=rs.get("complexity_low", 0),
        complexity_medium=rs.get("complexity_medium", 0),
    )
    return result["total_hours"], result["total_weeks"]


def _dependency_count(lineage: dict) -> int:
    """Count total import-level dependencies from dependency_graph."""
    dep_graph = lineage.get("dependency_graph", {})
    return sum(len(v.get("imports", [])) for v in dep_graph.values())


# ── Section renderers ─────────────────────────────────────────────────────────

def _render_metrics_grid(rs: dict) -> None:
    """Job Name / Source Count / Target Count / Component Count / Mapping Count / SQL / Java / Dependency."""
    from app.ui.design_system_v2 import render_kpi_row

    lineage = _load_lineage_cache()

    # Approximate source count = db_component types (inputs); target = db types (outputs)
    # Phase 1B tracks total DB components (245) across both input and output.
    # We split roughly: sources ≈ db + cloud inputs; targets ≈ db outputs.
    # Best available: sql_tables_detected for distinct table targets, db_comps for all DB
    source_count  = rs.get("total_db_comps", 0) + rs.get("total_cloud_comps", 0)  # all input connectors
    target_count  = rs.get("sql_tables_detected", 33)                               # distinct SQL table targets
    component_count = rs.get("total_components", 0)
    mapping_count   = rs.get("total_tmap_comps", 0)
    sql_objects     = rs.get("sql_tables_detected", 0)
    java_objects    = rs.get("total_java_comps", 0)
    dep_count       = _dependency_count(lineage)

    # Job name: from session state or project name
    project_name = st.session_state.get("wizard_uploaded_file_name", "")
    if not project_name:
        project_name = "TMA Analysis Repository"
    else:
        project_name = project_name.replace(".zip", "").replace("_", " ")

    st.markdown(
        '<p style="font-size:12px;font-weight:700;color:#64748b;'
        'text-transform:uppercase;letter-spacing:.06em;margin:0 0 8px;">Repository Metrics</p>',
        unsafe_allow_html=True,
    )

    # Row 1 — job identity + counts
    cols1 = st.columns(4)
    _metric_card(cols1[0], "Job Name",        project_name,         "#1d4ed8")
    _metric_card(cols1[1], "Source Count",    str(source_count),    "#0f766e")
    _metric_card(cols1[2], "Target Count",    str(target_count),    "#7c3aed")
    _metric_card(cols1[3], "Component Count", str(component_count), "#b45309")

    # Row 2 — objects + dependencies
    cols2 = st.columns(4)
    _metric_card(cols2[0], "Mapping Count",   str(mapping_count),  "#be123c")
    _metric_card(cols2[1], "SQL Objects",     str(sql_objects),    "#0369a1")
    _metric_card(cols2[2], "Java Objects",    str(java_objects),   "#92400e")
    _metric_card(cols2[3], "Dependency Count",str(dep_count),      "#374151")


def _metric_card(col, label: str, value: str, color: str = "#1d4ed8") -> None:
    """Render a single metric card inside a column."""
    with col:
        st.markdown(
            f"""
            <div style="
                background:#ffffff;
                border:1px solid #e2e8f0;
                border-left:3px solid {color};
                border-radius:8px;
                padding:10px 12px;
                min-height:72px;
                box-shadow:0 1px 2px rgba(15,23,42,.05);
                margin-bottom:10px;
            ">
                <div style="font-size:10px;font-weight:700;color:#64748b;
                    text-transform:uppercase;letter-spacing:.03em;">{label}</div>
                <div style="font-size:clamp(14px,1.8vw,20px);font-weight:800;
                    color:{color};margin-top:4px;overflow-wrap:anywhere;">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_score_cards(rs: dict, scores: list) -> None:
    """Complexity Score / Migration Readiness / Validation Score / Risk Score / Estimated Effort."""
    hours, weeks = _effort_estimate(rs)

    # Build a score lookup by dimension name
    score_map = {s["dimension"]: s for s in scores}

    complexity_score   = int(rs.get("avg_complexity_score", 0))
    migration_score    = int(rs.get("migration_readiness_score", 0))
    validation_score   = int(score_map.get("Analysis Coverage", {}).get("score", rs.get("analysis_coverage_score", 100)))
    risk_score_raw     = int(score_map.get("Risk Findings", {}).get("score", rs.get("risk_findings_score", 92)))
    # Invert risk score so higher = more risk (100 - risk_findings_score)
    risk_score         = 100 - risk_score_raw

    st.markdown(
        '<p style="font-size:12px;font-weight:700;color:#64748b;'
        'text-transform:uppercase;letter-spacing:.06em;margin:12px 0 8px;">Assessment Scores</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(5)

    def _score_card(col, label, score, color, suffix=""):
        rag = _score_to_rag(score)
        bg  = {"GREEN": "#eef7f2", "AMBER": "#fef8ee", "RED": "#fdf4f4"}.get(rag, "#f8fafc")
        fg  = _rag_color(rag)
        with col:
            st.markdown(
                f"""
                <div style="
                    background:{bg};
                    border:1px solid {fg}33;
                    border-radius:8px;
                    padding:10px 12px;
                    min-height:88px;
                    text-align:center;
                    margin-bottom:10px;
                ">
                    <div style="font-size:10px;font-weight:700;color:#64748b;
                        text-transform:uppercase;letter-spacing:.03em;">{label}</div>
                    <div style="font-size:clamp(18px,2.2vw,26px);font-weight:800;
                        color:{fg};margin-top:4px;">{score}{suffix}</div>
                    <div style="font-size:10px;font-weight:600;color:{fg};
                        margin-top:2px;">{rag}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    def _effort_card(col, hours, weeks):
        with col:
            st.markdown(
                f"""
                <div style="
                    background:#f0f4ff;
                    border:1px solid #3b82f633;
                    border-radius:8px;
                    padding:10px 12px;
                    min-height:88px;
                    text-align:center;
                    margin-bottom:10px;
                ">
                    <div style="font-size:10px;font-weight:700;color:#64748b;
                        text-transform:uppercase;letter-spacing:.03em;">Estimated Effort</div>
                    <div style="font-size:clamp(16px,2vw,22px);font-weight:800;
                        color:#1d4ed8;margin-top:4px;">{weeks}w</div>
                    <div style="font-size:10px;font-weight:600;color:#4f7ac7;
                        margin-top:2px;">{hours:,} hrs</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    _score_card(cols[0], "Complexity Score",    complexity_score, "#b45309")
    _score_card(cols[1], "Migration Readiness", migration_score,  "#15803d")
    _score_card(cols[2], "Validation Score",    validation_score, "#0f766e")
    _score_card(cols[3], "Risk Score",          risk_score,       "#be123c")
    _effort_card(cols[4], hours, weeks)


def _render_quick_insights(rs: dict) -> None:
    """Quick Insights panel with checkmarks and warnings."""
    total_jobs      = rs.get("total_jobs", 0)
    total_db        = rs.get("total_db_comps", 0)
    total_tmap      = rs.get("total_tmap_comps", 0)
    total_java      = rs.get("total_java_comps", 0)
    migration_score = rs.get("migration_readiness_score", 0)
    cloud_score     = rs.get("cloud_readiness_score", 0)
    deprecated_risk = rs.get("deprecated_risk_score", 100)

    # Derive unsupported count from session state if available, else estimate
    all_jobs = st.session_state.get("last_analysis_jobs", [])
    unsupported_count = sum(
        1 for j in all_jobs for r in j.get("enterprise_risk_report", [])
        if r.get("risk") in ("HIGH", "CRITICAL")
    ) if all_jobs else 0

    # Build insight items
    insights = []

    # ✓ green items
    if total_jobs > 0:
        insights.append(("✓", f"Sources Detected — {total_db} DB + cloud connectors across {total_jobs} modules", "GREEN"))
    if total_db > 0:
        insights.append(("✓", f"Targets Detected — {rs.get('sql_tables_detected', 0)} distinct SQL tables identified", "GREEN"))
    if total_tmap > 0:
        insights.append(("✓", f"Mappings Extracted — {total_tmap} tMap transformation mappings found", "GREEN"))
    if migration_score >= 70:
        insights.append(("✓", f"Migration Readiness — Score {migration_score}/100 (GREEN)", "GREEN"))
    if deprecated_risk >= 85:
        insights.append(("✓", f"Deprecated Risk Low — Component compatibility score {rs.get('component_compat_score', 0)}/100", "GREEN"))

    # ⚠ amber/red items
    if unsupported_count > 0:
        insights.append(("⚠", f"Unsupported Components — {unsupported_count} HIGH/CRITICAL risk findings require review", "AMBER"))
    elif total_java > 0:
        insights.append(("⚠", f"Java Complexity — {total_java} custom Java components (tJava, tJavaRow, tJavaFlex) detected", "AMBER"))
    if cloud_score < 80:
        insights.append(("⚠", f"Migration Risks — Cloud readiness score {cloud_score}/100; review cloud blockers", "AMBER"))
    if rs.get("dependency_complexity_score", 0) == 0:
        insights.append(("⚠", f"Dependency Complexity — Inter-module dependency analysis pending review", "AMBER"))

    st.markdown(
        '<p style="font-size:12px;font-weight:700;color:#64748b;'
        'text-transform:uppercase;letter-spacing:.06em;margin:12px 0 8px;">Quick Insights</p>',
        unsafe_allow_html=True,
    )

    _COLORS = {
        "GREEN": ("#15803d", "#eef7f2", "#a8d5bb"),
        "AMBER": ("#b45309", "#fef8ee", "#e5d09a"),
        "RED":   ("#be123c", "#fdf4f4", "#deb8b8"),
    }

    items_html = ""
    for icon, text, level in insights:
        fg, bg, border = _COLORS.get(level, ("#475569", "#f8fafc", "#dbe3ea"))
        icon_color = fg
        items_html += (
            f'<div style="display:flex;align-items:flex-start;gap:8px;'
            f'background:{bg};border:1px solid {border};border-radius:6px;'
            f'padding:7px 12px;margin-bottom:6px;">'
            f'<span style="font-size:14px;font-weight:800;color:{icon_color};'
            f'flex-shrink:0;margin-top:0px;">{icon}</span>'
            f'<span style="font-size:12px;color:#334155;line-height:1.5;">{text}</span>'
            f'</div>'
        )

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;'
        f'padding:14px 16px;">{items_html}</div>',
        unsafe_allow_html=True,
    )


def _render_ai_summary(rs: dict, scores: list) -> None:
    """AI Summary section — derived from cache metadata, no LLM calls."""
    from app.ui.design_system_v2 import render_kpi_row

    # Build structured summary from existing cache data
    top_comps = rs.get("top_components", {})
    top_comp_str = ", ".join(
        f"{k} ({v})" for k, v in list(top_comps.items())[:5]
    ) if top_comps else "N/A"

    score_map = {s["dimension"]: s for s in scores}
    migration_rag  = rs.get("migration_rag", "GREEN")
    cloud_score    = rs.get("cloud_readiness_score", 0)
    java_count     = rs.get("total_java_comps", 0)
    deprecated_score = rs.get("deprecated_risk_score", 100)
    component_compat = rs.get("component_compat_score", 0)
    total_jobs     = rs.get("total_jobs", 0)
    total_comps    = rs.get("total_components", 0)
    sql_tables     = rs.get("sql_tables_detected", 0)
    db_comps       = rs.get("total_db_comps", 0)
    cloud_comps    = rs.get("total_cloud_comps", 0)
    msg_comps      = rs.get("total_messaging_comps", 0)
    tmap_count     = rs.get("total_tmap_comps", 0)
    hours, weeks   = _effort_estimate(rs)

    # Risk level
    # Risk level — derived via canonical rag_from_score (>=80 GREEN / >=60 AMBER / <60 RED)
    _risk_rag  = _score_to_rag(rs.get("risk_findings_score", 92))
    risk_level = {"GREEN": "LOW", "AMBER": "MEDIUM", "RED": "HIGH"}.get(_risk_rag, "MEDIUM")
    risk_color = {"LOW": "#15803d", "MEDIUM": "#b45309", "HIGH": "#be123c"}.get(risk_level, "#475569")

    # Purpose
    purpose = (
        f"This Talend repository contains {total_jobs:,} modules with {total_comps:,} components, "
        f"implementing data integration and ETL workflows. The dominant patterns are {top_comp_str}. "
        f"The repository supports database ({db_comps} connectors), "
        f"cloud ({cloud_comps} components), and messaging ({msg_comps} components) integrations."
    )

    # Sources
    sources_text = (
        f"{db_comps} database component connectors spanning {sql_tables} distinct SQL tables "
        f"with {rs.get('unique_db_types', 0)} unique database types."
    )

    # Targets
    targets_text = (
        f"{sql_tables} SQL table targets detected, {cloud_comps} cloud-based output connectors, "
        f"and {msg_comps} messaging/streaming endpoints."
    )

    # Key Transformations
    transforms_text = (
        f"{tmap_count} tMap column-level transformation mappings, "
        f"{java_count} custom Java code blocks (tJava/tJavaRow/tJavaFlex), "
        f"and {rs.get('unique_component_types', 0)} unique component types in use."
    )

    # Risks
    rag_desc = {"GREEN": "is migration-ready", "AMBER": "needs targeted review", "RED": "requires significant remediation"}.get(migration_rag, "is under assessment")
    risks_text = (
        f"The repository {rag_desc} (readiness score {rs.get('migration_readiness_score', 0)}/100). "
        f"Cloud readiness is {cloud_score}/100. "
        f"{java_count} custom Java components introduce migration complexity. "
        f"Component compatibility is {component_compat}/100 with deprecated risk score {deprecated_score}/100."
    )

    # Recommendations
    rec_items = []
    if java_count > 0:
        rec_items.append(f"Review {java_count} custom Java components for migration compatibility")
    if cloud_score < 80:
        rec_items.append(f"Address cloud readiness gaps (score: {cloud_score}/100)")
    if component_compat < 90:
        rec_items.append(f"Replace deprecated components (compatibility: {component_compat}/100)")
    rec_items.append(f"Estimated migration effort: {hours:,} hours ({weeks} weeks)")
    recs_text = "; ".join(rec_items) if rec_items else "Repository is well-positioned for migration."

    st.markdown(
        '<p style="font-size:12px;font-weight:700;color:#64748b;'
        'text-transform:uppercase;letter-spacing:.06em;margin:12px 0 8px;">AI Summary</p>',
        unsafe_allow_html=True,
    )

    def _summary_row(icon: str, label: str, text: str, color: str = "#1d4ed8") -> str:
        return (
            f'<div style="display:flex;gap:10px;padding:10px 0;'
            f'border-bottom:1px solid #f1f5f9;">'
            f'<div style="min-width:20px;font-size:16px;">{icon}</div>'
            f'<div>'
            f'<div style="font-size:11px;font-weight:700;color:{color};'
            f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px;">{label}</div>'
            f'<div style="font-size:12px;color:#334155;line-height:1.6;">{text}</div>'
            f'</div></div>'
        )

    summary_html = (
        _summary_row("🎯", "Purpose",              purpose,        "#1d4ed8") +
        _summary_row("📥", "Sources",              sources_text,   "#0f766e") +
        _summary_row("📤", "Targets",              targets_text,   "#7c3aed") +
        _summary_row("🔀", "Key Transformations",  transforms_text,"#b45309") +
        _summary_row("⚠️", "Risks",               risks_text,     "#be123c") +
        _summary_row("✅", "Recommendations",      recs_text,      "#15803d")
    )

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;'
        f'border-radius:10px;padding:14px 18px;">'
        f'{summary_html}'
        f'<div style="font-size:10px;color:#94a3b8;margin-top:8px;">'
        f'Generated from Phase 1B/1C cache metadata — no LLM inference</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Main render entry point ───────────────────────────────────────────────────

def render_overview_dashboard() -> None:
    """
    Render the Overview Dashboard tab.

    Called from within the Home wizard's Overview tab context.
    Uses only Phase 1B/1C cache data — no new parsing or LLM calls.
    """
    rs     = _load_repository_summary()
    scores = _load_migration_scores()

    if not rs:
        st.info(
            "📊 Overview Dashboard is ready. "
            "Upload and analyze a repository to see metrics here."
        )
        return

    # ── Repository Metrics ────────────────────────────────────────────────────
    _render_metrics_grid(rs)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Assessment Scores ─────────────────────────────────────────────────────
    _render_score_cards(rs, scores)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Quick Insights + AI Summary side-by-side on wide screens ─────────────
    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_left:
        _render_quick_insights(rs)

    with col_right:
        _render_ai_summary(rs, scores)
