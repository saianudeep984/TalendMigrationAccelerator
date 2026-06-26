"""
Quick Insights Panel
====================
Renders a compact insights summary ABOVE all existing Job 360 tabs.
Injected at the top of render_job_analysis_page() — no existing code removed.

Uses ONLY already-computed data from the job entry dict and shared cache:
  - job["complexity"]            already computed by complexity_analyzer
  - job["legacy_risk_report"]    already computed by deprecated_checker
  - job["cloud_readiness"]       already computed at analysis time
  - job["enterprise_risk_report"] already computed by risk_engine
  - _inv  (build_source_target_inventory result, cached in _shared)
  - _all_recs  (auto_fix recommendations, cached in _shared)

Tab navigation uses st.session_state["_job360_active_tab"] + st.rerun().
The tab list in job_analysis_page.py must read this key (see patch below).
"""

from __future__ import annotations

import re
import streamlit as st

from app.ui.design_system_v2 import render_kpi_row, render_kpi_badge

# ── RAG helpers ───────────────────────────────────────────────────────────────

_RAG_COLORS = {
    "GREEN":  ("#15803d", "Migration Ready"),
    "AMBER":  ("#b45309", "Needs Review"),
    "RED":    ("#be123c", "High Risk"),
    "BLACK":  ("#111827", "Blocked"),
}

_COMPLEXITY_COLORS = {
    "LOW":      "#15803d",
    "MEDIUM":   "#b45309",
    "HIGH":     "#be123c",
    "CRITICAL": "#7c3aed",
}

_READINESS_LABEL = {
    "GREEN":  ("Migration Ready",   "#15803d", "#EAF3DE"),
    "AMBER":  ("Needs Review",      "#b45309", "#FAEEDA"),
    "RED":    ("High Risk",         "#be123c", "#FCEBEB"),
    "BLACK":  ("Blocked",           "#111827", "#E5E7EB"),
}


def _rag_from_cloud(cr: dict) -> str:
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    readiness = cr.get("readiness", "")
    if readiness == "HIGH":
        return "GREEN"
    if readiness == "MEDIUM":
        return "AMBER"
    if readiness == "LOW":
        return "RED"
    return "AMBER"


def _overall_readiness_rag(job: dict) -> str:
    """Derive a single RAG from existing computed fields — no re-scoring."""
    cx_level = (job.get("complexity") or {}).get("complexity", "LOW")
    cloud_rag = _rag_from_cloud(job.get("cloud_readiness") or {})
    risk_items = [
        r for r in (job.get("enterprise_risk_report") or [])
        if (r.get("risk") or "").upper() in ("HIGH", "CRITICAL")
    ]

    if cx_level == "CRITICAL" or len(risk_items) >= 5:
        return "BLACK"
    if cx_level == "HIGH" or cloud_rag == "RED" or len(risk_items) >= 2:
        return "RED"
    if cx_level == "MEDIUM" or cloud_rag == "AMBER" or risk_items:
        return "AMBER"
    return "GREEN"


# ── top-risk extraction ───────────────────────────────────────────────────────

_RISK_LABELS = {
    "tJava":         "Heavy tJava Usage",
    "tJavaRow":      "Heavy tJavaRow Usage",
    "tJavaFlex":     "Custom Java Flex",
    "tSystem":       "OS Command Execution (tSystem)",
    "tBeanShell":    "Deprecated BeanShell Scripting",
    "tLibraryLoad":  "External Library Dependency",
    "tDynamicSchema":"Dynamic Schema Usage",
    "tRunJob":       "Child Job Dependencies",
}

_HIGH_RISK_TYPES = {"tJava", "tJavaRow", "tJavaFlex", "tSystem", "tBeanShell", "tLibraryLoad"}


def _extract_top_risks(jd: dict, legacy_risks: list, enterprise_risks: list) -> list[str]:
    """Return up to 5 human-readable top risk strings from already-computed data."""
    risks: list[str] = []
    seen: set[str] = set()

    comp_types = {
        (c.get("component_type", "") if isinstance(c, dict) else str(c))
        for c in jd.get("components", [])
    }

    for ct in _HIGH_RISK_TYPES:
        if ct in comp_types and _RISK_LABELS[ct] not in seen:
            seen.add(_RISK_LABELS[ct])
            risks.append(_RISK_LABELS[ct])

    if "tDynamicSchema" in comp_types and "Dynamic Schema Usage" not in seen:
        seen.add("Dynamic Schema Usage")
        risks.append("Dynamic Schema Usage")

    # legacy_risks from deprecated_checker
    for lr in (legacy_risks or []):
        issue = (lr.get("details") or {}).get("issue", "")
        if issue and issue not in seen:
            seen.add(issue)
            risks.append(issue)

    # enterprise_risks — HIGH/CRITICAL only
    for er in (enterprise_risks or []):
        if (er.get("risk") or "").upper() in ("HIGH", "CRITICAL"):
            desc = er.get("description") or er.get("component") or ""
            if desc and desc not in seen:
                seen.add(desc)
                risks.append(desc)

    # Child job dependency
    child_count = sum(
        1 for c in jd.get("components", [])
        if (c.get("component_type", "") if isinstance(c, dict) else "") == "tRunJob"
    )
    if child_count > 0:
        label = f"Child Job Dependencies ({child_count})"
        if label not in seen:
            risks.append(label)

    return risks[:5]


# ── joblet / routine counts from components ───────────────────────────────────

def _count_joblets_routines(jd: dict) -> tuple[int, int]:
    seen_joblets: set[str] = set()
    routine_names: set[str] = set()
    for c in jd.get("components", []):
        ctype = c.get("component_type", "") if isinstance(c, dict) else ""
        params = c.get("parameters", {}) if isinstance(c, dict) else {}
        if ctype.lower().startswith("tjoblet") or ctype == "tJoblet":
            jn = (
                params.get("JOBLET") or params.get("PROCESS")
                or c.get("unique_name", "") or ctype
            )
            if jn:
                seen_joblets.add(jn)
        for val in params.values():
            for rname in re.findall(r"\b([A-Z][A-Za-z0-9_]{2,})\s*\.", str(val)):
                routine_names.add(rname)
    return len(seen_joblets), len(routine_names)


# ── main render ───────────────────────────────────────────────────────────────

def render_quick_insights(
    job: dict,
    jd: dict,
    inv: dict,
    all_recs: list,
    job_name: str,
) -> None:
    """
    Render the Quick Insights panel.

    Parameters
    ----------
    job       : full job entry from last_analysis_jobs
    jd        : job["job_data"]
    inv       : build_source_target_inventory result (already cached in _shared)
    all_recs  : generate_auto_fix_recommendations result (already cached in _shared)
    job_name  : str
    """

    # ── Collect pre-computed values ───────────────────────────────────────────
    cx          = job.get("complexity") or {}
    cx_level    = cx.get("complexity", "LOW")
    cx_score    = cx.get("score", 0)

    cloud       = job.get("cloud_readiness") or {}
    cloud_rag   = _rag_from_cloud(cloud)

    leg_risks   = job.get("legacy_risk_report") or []
    ent_risks   = job.get("enterprise_risk_report") or []
    overall_rag = _overall_readiness_rag(job)

    components     = jd.get("components", [])
    ctx_vars       = jd.get("contexts", [])
    sql_ops        = inv.get("sql_operations", [])
    sources        = inv.get("sources", [])
    targets        = inv.get("targets", [])
    n_joblets, n_routines = _count_joblets_routines(jd)

    job_recs    = [r for r in all_recs if r.get("job_name") == job_name]
    top_risks   = _extract_top_risks(jd, leg_risks, ent_risks)

    readiness_label, readiness_fg, readiness_bg = _READINESS_LABEL.get(
        overall_rag, ("Unknown", "#5f5e5a", "#F1EFE8")
    )

    # ── Panel header ──────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="
            border:0.5px solid #d1d0c8;
            border-radius:12px;
            padding:14px 18px 10px;
            margin-bottom:14px;
            background:#ffffff;
        ">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
            <span style="font-size:13px;font-weight:600;color:#1a1a18;">⚡ Quick Insights</span>
            <span style="
                background:{readiness_bg};color:{readiness_fg};
                font-size:11px;font-weight:700;
                padding:3px 12px;border-radius:999px;
            ">{readiness_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Row 1: Scores ─────────────────────────────────────────────────────────
    cx_color = _COMPLEXITY_COLORS.get(cx_level, "#5f5e5a")
    cloud_color = _RAG_COLORS.get(cloud_rag, ("#5f5e5a", ""))[0]

    render_kpi_row([
        {"label": "Complexity",   "value": cx_level,       "caption": f"Score {cx_score}", "color": cx_color},
        {"label": "Cloud Ready",  "value": cloud_rag,      "caption": cloud.get("status", ""), "color": cloud_color},
        {"label": "Risk Items",   "value": len(ent_risks),  "caption": f"{len(top_risks)} critical", "color": "#be123c" if top_risks else "#15803d"},
        {"label": "Auto-Fix",     "value": len([r for r in job_recs if r.get("auto_fix")]),
                                   "caption": f"of {len(job_recs)} findings", "color": "#1d4ed8"},
    ])

    # ── Row 2: Counts ─────────────────────────────────────────────────────────
    render_kpi_row([
        {"label": "Components",   "value": len(components), "caption": "total",          "color": "#1d4ed8"},
        {"label": "Context Vars", "value": len(ctx_vars),   "caption": "variables",      "color": "#0f6e56"},
        {"label": "Joblets",      "value": n_joblets,       "caption": "used",           "color": "#534AB7"},
        {"label": "Routines",     "value": n_routines,      "caption": "referenced",     "color": "#854F0B"},
        {"label": "SQL Ops",      "value": len(sql_ops),    "caption": "operations",     "color": "#0C447C"},
        {"label": "Sources",      "value": len(sources),    "caption": "source systems", "color": "#3B6D11"},
        {"label": "Targets",      "value": len(targets),    "caption": "target systems", "color": "#712B13"},
    ])

    # ── Top risks ─────────────────────────────────────────────────────────────
    if top_risks:
        st.markdown(
            '<p style="font-size:12px;font-weight:600;color:#5f5e5a;margin:8px 0 4px;">Top Migration Risks</p>',
            unsafe_allow_html=True,
        )
        risk_html = "".join(
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'background:#FCEBEB;color:#A32D2D;font-size:11px;font-weight:600;'
            f'padding:3px 10px;border-radius:999px;margin:2px 4px 2px 0;">'
            f'⚠ {r}</span>'
            for r in top_risks
        )
        st.markdown(f'<div style="margin-bottom:6px;">{risk_html}</div>', unsafe_allow_html=True)

    # ── Quick-nav links ───────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    # Tab indices match the st.tabs() order in job_analysis_page.py:
    # 0=Executive, 1=Summary, 2=Functional, 3=SQL, 4=Flowcharts,
    # 5=Data Flow, 6=Dependencies, 7=Migration, 8=Java, 9=AI Copilot,
    # 10=Column Mapping, 11=Lineage
    with col1:
        if st.button("📊 View Readiness Breakdown", key=f"qi_readiness_{job_name}", use_container_width=True):
            st.session_state["_job360_active_tab"] = 7   # Migration tab
            st.rerun()
    with col2:
        if st.button("🧭 View Lineage", key=f"qi_lineage_{job_name}", use_container_width=True):
            st.session_state["_job360_active_tab"] = 11  # Lineage tab
            st.rerun()
    with col3:
        if st.button("📄 View Documentation", key=f"qi_docs_{job_name}", use_container_width=True):
            # Navigate to Documentation Hub with this job pre-selected
            from app.ui.design_system_v2 import _NAV_PAGES
            doc_idx = next((i for i, (k, _) in enumerate(_NAV_PAGES) if k == "documentation_hub"), 5)
            st.session_state["_nav_idx2"] = doc_idx
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
