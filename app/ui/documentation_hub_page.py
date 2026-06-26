"""
Documentation Hub — Enterprise Redesign
Matches Job 360 design language: header, KPI cards, phase workflow cards,
tab bar, sticky toolbar. No radio buttons, no white space, no page reloads.
Integrates all existing generators, export framework, and section renderers.
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st
from app.utils.safe_access import sanitize_dataframe_for_streamlit as _safe_df

from app.ui.design_system_v2 import (
    empty_state_card,
    metric_card,
    page_header,
    pdf_download_button,
)

# ── Constants ─────────────────────────────────────────────────────────────────

_CATEGORIES = {
    "Technical Documents":    ["TDD", "LLD"],
    "Migration Documents":    ["Migration Report", "Migration Runbook"],
    "Executive Documents":    ["Executive Report"],
    "Validation Documents":   ["Testing Architecture"],
    "Architecture Documents": ["Architecture Report"],
}

_DOC_CARDS = [
    ("📄", "TDD",          "tdd",          "Technical Design Document",
     "Repository, jobs, complexity, lineage and recommendations."),
    ("📐", "LLD",          "lld",          "Low-Level Design",
     "Components, schemas, column mapping and configuration."),
    ("📋", "Runbook",      "runbooks",     "Migration Runbook",
     "Pre-checks, cutover, validation, rollback playbook."),
    ("🏛️", "Architecture", "architecture", "Architecture Report",
     "Auto-fixes, cloud readiness, integration map."),
    ("📈", "Executive",    "reports",      "Executive Report",
     "Cost, timeline, KPIs, risk and roadmap for stakeholders."),
    ("🗂️", "Migration",    "reports",      "Migration Report",
     "Wave planning, intelligence and impact analysis."),
    ("🧪", "Validation",   "reports",      "Validation Report",
     "Coverage, quality gates, defects and sign-off."),
]

_STATUS_GENERATED   = "Generated"
_STATUS_IN_PROGRESS = "In Progress"
_STATUS_FAILED      = "Failed"
_STATUS_PENDING     = "Pending"

# Phase workflow cards — matches Job 360 colour palette exactly
_DOC_PHASES = [
    {"id": "tdd",          "label": "TDD",          "icon": "📄",
     "color": "#2563EB", "bg": "#EFF6FF", "border": "#2563EB"},
    {"id": "lld",          "label": "LLD",          "icon": "📐",
     "color": "#16A34A", "bg": "#F0FDF4", "border": "#16A34A"},
    {"id": "runbooks",     "label": "Runbook",      "icon": "📋",
     "color": "#EA580C", "bg": "#FFF7ED", "border": "#EA580C"},
    {"id": "architecture", "label": "Architecture", "icon": "🏛️",
     "color": "#7C3AED", "bg": "#F5F3FF", "border": "#7C3AED"},
    {"id": "reports",      "label": "Executive",    "icon": "📈",
     "color": "#D97706", "bg": "#FFFBEB", "border": "#D97706"},
    {"id": "reports_mig",  "label": "Migration",    "icon": "🗂️",
     "color": "#0284C7", "bg": "#F0F9FF", "border": "#0284C7"},
    {"id": "exports",      "label": "Exports",      "icon": "⬇️",
     "color": "#9333EA", "bg": "#FDF4FF", "border": "#9333EA"},
]

_DOC_ORDER = ["tdd", "lld", "runbooks", "architecture", "reports", "exports"]


# ── CSS ───────────────────────────────────────────────────────────────────────

_DOCHUB_CSS = """
<style>
/* ── Documentation Hub Styles — matches Job 360 ── */

/* Header */
.dh-header {
    display: flex;
    align-items: center;
    gap: 16px;
    background: linear-gradient(120deg, #0b1d3a 0%, #1d4ed8 100%);
    color: #fff;
    border-radius: 14px;
    padding: 20px 24px;
    margin: 0 0 16px 0;
    box-shadow: 0 2px 12px rgba(15,23,42,.12);
}
.dh-header-icon {
    width: 52px; height: 52px;
    border-radius: 14px;
    background: rgba(255,255,255,.18);
    display: flex; align-items: center; justify-content: center;
    font-size: 26px;
    flex-shrink: 0;
}
.dh-header-title  { font-size: 22px; font-weight: 800; letter-spacing: .01em; }
.dh-header-sub    { font-size: 13px; opacity: .8; margin-top: 3px; }

/* KPI row — exactly like Job 360 executive metrics */
.dh-kpi-section-label {
    font-size: 10px; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; color: #94A3B8;
    margin: 4px 0 8px 2px;
}

/* Tab bar — matches Job 360 tab style */
.dh-tabs-wrap {
    display: flex;
    gap: 0;
    border-bottom: 2px solid #e2e8f0;
    margin: 12px 0 0 0;
    overflow-x: auto;
}
.dh-tab {
    padding: 10px 16px 10px;
    font-size: 13px; font-weight: 600;
    color: #64748b;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    white-space: nowrap;
    transition: color .15s, border-color .15s;
}
.dh-tab:hover  { color: #1d4ed8; }
.dh-tab.active { color: #1d4ed8; border-bottom-color: #1d4ed8; font-weight: 700; }

/* Phase workflow cards — mirrors Job 360 "Migration Phase Overview" */
.dh-phase-wrap {
    display: flex;
    align-items: stretch;
    gap: 0;
    width: 100%;
    overflow-x: hidden;
    padding: 14px 0 18px;
    box-sizing: border-box;
}
.dh-phase {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    position: relative;
    cursor: pointer;
}
.dh-phase-connector {
    display: flex; align-items: flex-start;
    padding-top: 28px; flex-shrink: 0; width: 22px;
}
.dh-phase-header {
    display: flex; flex-direction: column;
    align-items: center; gap: 6px;
    padding: 10px 8px 8px;
    border-radius: 12px 12px 0 0;
    border: 1px solid;
    box-sizing: border-box;
}
.dh-phase-icon {
    width: 42px; height: 42px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
    color: #fff;
}
.dh-phase-title {
    font-size: 11px; font-weight: 700;
    letter-spacing: .06em; text-transform: uppercase;
}
.dh-phase-body {
    flex: 1;
    border-radius: 0 0 12px 12px;
    border-width: 0 1px 1px 1px;
    border-style: solid;
    padding: 8px 8px 10px;
    box-sizing: border-box;
}
.dh-phase-item {
    display: flex; align-items: flex-start; gap: 6px;
    font-size: 11px; color: #334155;
    padding: 4px 2px; border-bottom: 1px solid rgba(0,0,0,.05);
}
.dh-phase-item:last-child { border-bottom: none; }
.dh-phase-num {
    font-size: 9px; font-weight: 700; color: #94A3B8;
    flex-shrink: 0; margin-top: 1px; width: 12px;
}
.dh-phase-item-title { font-weight: 600; }
.dh-phase-item-desc  { font-size: 10px; color: #64748b; margin-top: 1px; }
.dh-phase.active .dh-phase-header {
    box-shadow: 0 4px 12px rgba(0,0,0,.15);
}

/* Status pill */
.dh-pill {
    display: inline-block;
    padding: 2px 8px; border-radius: 99px;
    font-size: 10px; font-weight: 700;
}
.dh-pill-ready   { background: #dcfce7; color: #15803d; }
.dh-pill-pending { background: #fef3c7; color: #92400e; }
.dh-pill-prog    { background: #dbeafe; color: #1d4ed8; }
.dh-pill-fail    { background: #fee2e2; color: #be123c; }

/* Export center cards — mirrors Job 360 card grid */
.dh-export-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px,1fr));
    gap: 14px;
    margin: 10px 0 18px;
}
.dh-export-card {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    cursor: pointer;
    transition: all .15s;
    border-top: 3px solid;
}
.dh-export-card:hover {
    box-shadow: 0 6px 18px rgba(29,78,216,.08);
    transform: translateY(-1px);
}
.dh-export-card-icon  { font-size: 26px; margin-bottom: 8px; }
.dh-export-card-title { font-size: 14px; font-weight: 700; color: #0f172a; }
.dh-export-card-desc  { font-size: 11px; color: #64748b; margin-top: 4px; line-height: 1.4; }
.dh-export-card-meta  { margin-top: 10px; display: flex; justify-content: space-between; align-items: center; }

/* Sticky bottom toolbar */
.dh-toolbar {
    position: sticky; bottom: 0; z-index: 20;
    background: rgba(255,255,255,.94);
    backdrop-filter: blur(10px);
    border-top: 1px solid #e2e8f0;
    border-radius: 12px 12px 0 0;
    padding: 10px 16px; margin-top: 20px;
    box-shadow: 0 -4px 14px rgba(15,23,42,.04);
}

/* Generation tracker */
.dh-gen-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px,1fr));
    gap: 8px; margin: 8px 0 14px;
}
.dh-gen-tile {
    border: 1px solid;
    border-radius: 8px;
    padding: 8px 10px;
}
.dh-gen-status { font-size: 11px; font-weight: 700; }
.dh-gen-label  { font-size: 12px; color: #334155; margin-top: 2px; }

/* Section label */
.dh-section-label {
    font-size: 10px; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; color: #94A3B8;
    margin: 16px 0 8px 2px;
}
</style>
"""


def _inject_css() -> None:
    st.markdown(_DOCHUB_CSS, unsafe_allow_html=True)


# ── Generation Status ─────────────────────────────────────────────────────────

def _get_generation_status() -> dict[str, str]:
    jobs   = st.session_state.get("last_analysis_jobs", [])
    status: dict[str, str] = {}
    status["TDD"]              = _STATUS_GENERATED  if jobs else _STATUS_PENDING
    status["LLD"]              = _STATUS_GENERATED  if jobs else _STATUS_PENDING
    status["Migration Runbook"]= _STATUS_GENERATED  if st.session_state.get("migration_runbook") else _STATUS_PENDING
    status["Architecture"]     = _STATUS_GENERATED  if st.session_state.get("architecture_autofix_intelligence") else _STATUS_PENDING
    status["Executive Report"] = _STATUS_GENERATED  if st.session_state.get("executive_dashboard_model") else _STATUS_PENDING
    status["Migration Report"] = _STATUS_GENERATED  if st.session_state.get("migration_intelligence") else _STATUS_PENDING
    status["Validation"]       = _STATUS_GENERATED  if jobs else _STATUS_PENDING
    for k in st.session_state:
        if k.startswith("_gen_fail_"):
            status[k[len("_gen_fail_"):]] = _STATUS_FAILED
    return status


def _render_generation_tracker() -> None:
    status = _get_generation_status()
    color_map = {
        _STATUS_GENERATED:   ("#22c55e", "dh-pill-ready"),
        _STATUS_IN_PROGRESS: ("#f59e0b", "dh-pill-prog"),
        _STATUS_FAILED:      ("#ef4444", "dh-pill-fail"),
        _STATUS_PENDING:     ("#94a3b8", "dh-pill-pending"),
    }
    icon_map = {
        _STATUS_GENERATED: "✅", _STATUS_IN_PROGRESS: "⏳",
        _STATUS_FAILED: "❌", _STATUS_PENDING: "🕐",
    }
    tiles = ""
    for doc_type, state in status.items():
        clr, _ = color_map.get(state, ("#94a3b8", ""))
        icon   = icon_map.get(state, "❓")
        tiles += (
            f'<div class="dh-gen-tile" style="border-color:{clr};background:{clr}18;">'
            f'<div class="dh-gen-status" style="color:{clr};">{icon} {state}</div>'
            f'<div class="dh-gen-label">{html.escape(doc_type)}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="dh-gen-grid">{tiles}</div>', unsafe_allow_html=True)


# ── Document Registry ─────────────────────────────────────────────────────────

def _build_document_registry() -> list[dict]:
    docs: list[dict] = []
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    jobs = st.session_state.get("last_analysis_jobs", [])
    repo_name = st.session_state.get("last_repo_name", "—")

    for j in jobs:
        jname = j.get("job_data", {}).get("job_name", "Unknown")
        docs.append({"Document Name": f"TDD – {jname}", "Document Type": "TDD",
                     "Category": "Technical Documents", "Generated Date": now,
                     "Repository": repo_name, "Status": "Available",
                     "_source": "tdd", "_job": jname})
    if jobs:
        docs.append({"Document Name": "LLD – Component & Column Mapping", "Document Type": "LLD",
                     "Category": "Technical Documents", "Generated Date": now,
                     "Repository": repo_name, "Status": "Available",
                     "_source": "lld", "_job": None})
    if st.session_state.get("migration_runbook"):
        docs.append({"Document Name": "Migration Runbook", "Document Type": "Migration Runbook",
                     "Category": "Migration Documents", "Generated Date": now,
                     "Repository": repo_name, "Status": "Available",
                     "_source": "runbook", "_job": None})
    if st.session_state.get("architecture_autofix_intelligence"):
        docs.append({"Document Name": "Architecture Intelligence Report", "Document Type": "Architecture Report",
                     "Category": "Architecture Documents", "Generated Date": now,
                     "Repository": repo_name, "Status": "Available",
                     "_source": "architecture", "_job": None})
    if st.session_state.get("executive_dashboard_model"):
        for rpt in ["Executive Summary Report", "Cost Estimation Report", "Timeline Report",
                    "Resource Planning Report", "Migration Assessment Report", "Roadmap Report"]:
            docs.append({"Document Name": rpt, "Document Type": "Executive Report",
                         "Category": "Executive Documents", "Generated Date": now,
                         "Repository": repo_name, "Status": "Available",
                         "_source": "executive", "_job": None})
    if st.session_state.get("migration_intelligence"):
        docs.append({"Document Name": "Migration Intelligence Report", "Document Type": "Migration Report",
                     "Category": "Migration Documents", "Generated Date": now,
                     "Repository": repo_name, "Status": "Available",
                     "_source": "migration_intelligence", "_job": None})
    if st.session_state.get("impact_intelligence"):
        docs.append({"Document Name": "Impact Intelligence Report", "Document Type": "Migration Report",
                     "Category": "Migration Documents", "Generated Date": now,
                     "Repository": repo_name, "Status": "Available",
                     "_source": "impact_intelligence", "_job": None})
    if st.session_state.get("wizard_report_file"):
        docs.append({"Document Name": "Migration Analysis Excel Report", "Document Type": "Migration Report",
                     "Category": "Migration Documents", "Generated Date": now,
                     "Repository": repo_name, "Status": "Available",
                     "_source": "excel", "_job": None})
    return docs


# ── KPI Cards (exactly like Job 360 Executive Metrics) ────────────────────────

def _render_kpi_cards(docs: list[dict]) -> None:
    jobs        = st.session_state.get("last_analysis_jobs", [])
    gen_count   = sum(1 for d in docs if d.get("Status") == "Available")
    gen_status  = _get_generation_status()
    gen_ready   = sum(1 for v in gen_status.values() if v == _STATUS_GENERATED)
    pkg_ready   = gen_ready >= 3

    st.markdown('<div class="dh-kpi-section-label">Documentation Metrics</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Total Documents", str(len(docs)) or "0", f"{len(_DOC_CARDS)} document types", "blue")
    with c2:
        metric_card("Generated", str(gen_count), f"{gen_ready} of 7 ready", "green" if gen_count > 0 else "gray")
    with c3:
        metric_card("Export Formats", "4", "PDF · DOCX · HTML · ZIP", "purple")
    with c4:
        metric_card("Documentation Package", "Ready" if pkg_ready else "Pending",
                    "Package export available" if pkg_ready else "Generate documents first",
                    "green" if pkg_ready else "amber")


# ── Phase Workflow Cards (mirrors Job 360 Migration Phase Overview) ────────────

def _doc_status_for(section_key: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Return (status_label, css_class, [(item_title, item_desc), ...])"""
    jobs = st.session_state.get("last_analysis_jobs") or []
    has  = bool(jobs)

    items_map: dict[str, list[tuple[str, str]]] = {
        "tdd": [
            ("Job Architecture",    f"{len(jobs)} job(s) analysed" if jobs else "Load repository"),
            ("Source / Target",     "Tables, schemas, connections"),
            ("Complexity Profile",  "Score, risk items"),
            ("Column Lineage",      "tMap transformations"),
            ("Recommendations",     "AI-powered suggestions"),
        ],
        "lld": [
            ("Component Map",       "43 components mapped"),
            ("Schema Design",       "Tables and columns"),
            ("Column Mapping",      "Source → target lineage"),
            ("tMap Logic",          "Transformation detail"),
            ("Config Parameters",   "Context variables"),
        ],
        "runbooks": [
            ("Pre-migration Checks","Readiness validation"),
            ("Migration Waves",     "Phase-by-phase plan"),
            ("Cutover Procedure",   "Go-live steps"),
            ("Rollback Plan",       "Emergency recovery"),
            ("Validation Tasks",    "Post-migration checks"),
        ],
        "architecture": [
            ("Anti-patterns",       "Detected design issues"),
            ("Scorecard",           "Architecture health score"),
            ("Best Practices",      "Compliance checks"),
            ("Technical Debt",      "Remediation effort"),
            ("Auto-fix Map",        "Cloud readiness"),
        ],
        "reports": [
            ("Executive Summary",   "Cost & timeline KPIs"),
            ("Migration Assessment","Readiness & risk"),
            ("Roadmap",             "Milestone plan"),
            ("Resource Planning",   "Team & effort"),
            ("Stakeholder Deck",    "C-level overview"),
        ],
        "reports_mig": [
            ("Wave Planning",       "Migration batches"),
            ("Impact Analysis",     "Data & business impact"),
            ("Intelligence Report", "AI insights"),
            ("Validation Report",   "Test coverage"),
            ("Sign-off Pack",       "Quality gate"),
        ],
        "exports": [
            ("PDF Package",         "All docs as PDF"),
            ("DOCX Bundle",         "Editable Word docs"),
            ("HTML Export",         "Web-ready with assets"),
            ("ZIP Archive",         "Complete package"),
            ("Excel Report",        "Data & analytics"),
        ],
    }

    ready_map = {
        "tdd":         has,
        "lld":         has,
        "runbooks":    bool(st.session_state.get("migration_runbook")),
        "architecture":bool(st.session_state.get("architecture_autofix_intelligence")),
        "reports":     bool(st.session_state.get("executive_dashboard_model")),
        "reports_mig": bool(st.session_state.get("migration_intelligence")),
        "exports":     has,
    }
    ready = ready_map.get(section_key, has)
    items = items_map.get(section_key, [("Content", "Available")])
    status = "Ready" if ready else "Pending"
    css    = "dh-pill-ready" if ready else "dh-pill-pending"
    return status, css, items


def _render_phase_workflow_cards(current_section: str) -> None:
    st.markdown('<div class="dh-section-label">Migration Phase Overview</div>', unsafe_allow_html=True)

    connector_svg = (
        '<svg viewBox="0 0 24 16" xmlns="http://www.w3.org/2000/svg" '
        'width="22" height="16" style="display:block;">'
        '<line x1="2" y1="8" x2="18" y2="8" stroke="#CBD5E1" stroke-width="2" stroke-linecap="round"/>'
        '<polyline points="13,3 21,8 13,13" fill="none" stroke="#CBD5E1" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )

    phases_html = '<div class="dh-phase-wrap">'
    for i, phase in enumerate(_DOC_PHASES):
        pid        = phase["id"]
        clr        = phase["color"]
        bg         = phase["bg"]
        border     = phase["border"]
        icon       = phase["icon"]
        label      = phase["label"]
        # map "reports_mig" → "reports" for active check
        active_key = "reports" if pid == "reports_mig" else pid
        is_active  = current_section == active_key
        status, css, items = _doc_status_for(pid)

        # Active glow
        header_extra = 'box-shadow:0 4px 14px rgba(0,0,0,.18);' if is_active else ''

        items_html = ""
        for idx, (title, desc) in enumerate(items[:5], 1):
            items_html += (
                f'<div class="dh-phase-item">'
                f'<div class="dh-phase-num">#{idx}</div>'
                f'<div><div class="dh-phase-item-title">{html.escape(title)}</div>'
                f'<div class="dh-phase-item-desc">{html.escape(desc)}</div></div>'
                f'</div>'
            )

        pill = f'<span class="dh-pill {css}">{html.escape(status)}</span>'

        phases_html += (
            f'<div class="dh-phase">'
            f'<div class="dh-phase-header" style="background:{bg};border-color:{border};{header_extra}">'
            f'  <div class="dh-phase-icon" style="background:{clr};">{icon}</div>'
            f'  <div class="dh-phase-title" style="color:{clr};">{html.escape(label)}</div>'
            f'  {pill}'
            f'</div>'
            f'<div class="dh-phase-body" style="background:{bg};border-color:{border};">'
            f'  {items_html}'
            f'</div>'
            f'</div>'
        )
        if i < len(_DOC_PHASES) - 1:
            phases_html += (
                f'<div class="dh-phase-connector">{connector_svg}</div>'
            )

    phases_html += '</div>'
    st.markdown(phases_html, unsafe_allow_html=True)


# ── Tab Bar ────────────────────────────────────────────────────────────────────

def _render_tab_bar(current_section: str) -> str:
    """Horizontal tab bar — TDD only (overview removed)."""
    tabs = [
        ("📄",  "TDD",          "tdd"),
        # ("🏠",  "Overview",     "overview"),   # removed per design update
        # ("📐",  "LLD",          "lld"),        # hidden
        # ("📋",  "Runbook",      "runbooks"),   # hidden
        # ("🏛️", "Architecture",  "architecture"), # hidden
        # ("📈",  "Reports",      "reports"),    # hidden
        # ("⬇️",  "Exports",      "exports"),    # hidden
        # ("🔍",  "Search",       "search"),     # hidden
    ]

    # Use st.segmented_control (native tab feel)
    labels  = [f"{icon} {label}" for icon, label, _ in tabs]
    sections= [key for _, _, key in tabs]

    try:
        current_label = labels[sections.index(current_section)] if current_section in sections else labels[0]
        choice = st.segmented_control(
            "Navigate", labels,
            default=current_label,
            key="dh_tab_bar_v3",
            label_visibility="collapsed",
        )
        if choice:
            new_section = sections[labels.index(choice)]
            if new_section != current_section:
                st.session_state["doc_hub_section"] = new_section
                st.rerun()
            return new_section
    except Exception:
        pass
    return current_section


# ── Sidebar Navigation ────────────────────────────────────────────────────────

def _doc_sidebar() -> str:
    st.sidebar.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
        'letter-spacing:.08em;margin:8px 0 4px;">Documentation Hub</div>',
        unsafe_allow_html=True,
    )
    _SIDEBAR = [
        ("📄", "TDD",          "tdd"),
        # ("🏠", "Overview",     "overview"),      # removed per design update
        # ("📐", "LLD",          "lld"),           # hidden
        # ("📋", "Runbooks",     "runbooks"),      # hidden
        # ("🏛️", "Architecture", "architecture"),  # hidden
        # ("📈", "Reports",      "reports"),       # hidden
        # ("⬇️", "Exports",      "exports"),       # hidden
        # ("🔍", "Search",       "search"),        # hidden
    ]
    current = st.session_state.get("doc_hub_section", "tdd")
    for icon, label, key in _SIDEBAR:
        btn_type = "primary" if current == key else "secondary"
        if st.sidebar.button(f"{icon} {label}", key=f"dochub_nav_{key}",
                             type=btn_type, use_container_width=True):
            st.session_state["doc_hub_section"] = key
            st.rerun()
    return current


# ── Quick Actions ─────────────────────────────────────────────────────────────

def _render_quick_actions() -> None:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        return
    st.markdown('<div class="dh-section-label">Quick Actions</div>', unsafe_allow_html=True)
    qa_cols = st.columns(5)
    with qa_cols[0]:
        if st.button("📄 TDD", key="qa_tdd", use_container_width=True):
            st.session_state["doc_hub_section"] = "tdd"; st.rerun()
    with qa_cols[1]:
        if st.button("📐 LLD", key="qa_lld", use_container_width=True):
            st.session_state["doc_hub_section"] = "lld"; st.rerun()
    with qa_cols[2]:
        if st.button("📋 Runbook", key="qa_runbook", use_container_width=True):
            if not st.session_state.get("migration_runbook"):
                with st.spinner("Building runbook…"):
                    try:
                        from app.ui.migration_runbook_dashboard import build_migration_runbook
                        rb = build_migration_runbook(jobs, st.session_state.get("upgrade_advisor"))
                        st.session_state["migration_runbook"] = rb
                    except Exception as e:
                        st.session_state["_gen_fail_Migration Runbook"] = str(e)
            st.session_state["doc_hub_section"] = "runbooks"; st.rerun()
    with qa_cols[3]:
        if st.button("📈 Executive", key="qa_exec", use_container_width=True):
            st.session_state["doc_hub_section"] = "reports"; st.rerun()
    with qa_cols[4]:
        if st.button("⬇️ Export All", key="qa_export", use_container_width=True):
            st.session_state["doc_hub_section"] = "exports"; st.rerun()


# ── Document Preview ──────────────────────────────────────────────────────────

def _track_download(docname: str) -> None:
    counts = st.session_state.get("_doc_dl_counts", {})
    counts[docname] = counts.get(docname, 0) + 1
    st.session_state["_doc_dl_counts"] = counts


def _render_document_preview(doc: dict) -> None:
    src     = doc.get("_source", "")
    docname = doc.get("Document Name", "Document")
    jobs    = st.session_state.get("last_analysis_jobs", [])

    with st.expander(f"👁️ Preview: {docname}", expanded=True):
        meta_col, action_col = st.columns([2, 1])
        with meta_col:
            st.markdown("**📋 Metadata**")
            for k, v in doc.items():
                if not k.startswith("_"):
                    st.markdown(f"- **{k}:** {v}")
        with action_col:
            st.markdown("**⚡ Actions**")
            if src == "runbook":
                runbook = st.session_state.get("migration_runbook")
                if runbook:
                    from app.ui.migration_runbook_dashboard import export_runbook
                    _track_download(docname)
                    st.download_button("⬇️ Download JSON", data=export_runbook(runbook, "json"),
                                       file_name="migration_runbook.json",
                                       key=f"prev_dl_{src}", use_container_width=True)
                if st.button("🔄 Regenerate", key=f"prev_regen_{src}", use_container_width=True):
                    st.session_state.pop("migration_runbook", None)
                    with st.spinner("Regenerating…"):
                        try:
                            from app.ui.migration_runbook_dashboard import build_migration_runbook
                            rb = build_migration_runbook(jobs, st.session_state.get("upgrade_advisor"))
                            st.session_state["migration_runbook"] = rb
                            st.success("Regenerated.")
                        except Exception as e:
                            st.error(f"Failed: {e}")
            elif src == "architecture":
                arch_data = st.session_state.get("architecture_autofix_intelligence")
                if arch_data:
                    from app.ui.architecture_intelligence_dashboard import export_architecture_autofix
                    jdata = export_architecture_autofix(arch_data, "json")
                    if jdata:
                        _track_download(docname)
                        st.download_button("⬇️ Download JSON", data=jdata,
                                           file_name="architecture_report.json",
                                           key=f"prev_dl_{src}", use_container_width=True)
            elif src == "migration_intelligence":
                mi = st.session_state.get("migration_intelligence")
                if mi:
                    from app.ui.migration_intelligence_dashboard import export_migration_intelligence
                    jdata = export_migration_intelligence(mi, "json")
                    if jdata:
                        _track_download(docname)
                        st.download_button("⬇️ Download JSON", data=jdata,
                                           file_name="migration_intelligence.json",
                                           key=f"prev_dl_{src}", use_container_width=True)
            elif src in ("tdd", "lld"):
                st.info("Navigate to the section to view and download.")
                if st.button(f"→ Go to {src.upper()}", key=f"prev_nav_{src}", use_container_width=True):
                    st.session_state["doc_hub_section"] = src; st.rerun()
            else:
                st.caption("Use the Exports section to download.")


# ── Section: Overview ─────────────────────────────────────────────────────────

def _render_recent_documents(docs: list[dict]) -> None:
    if not docs:
        return
    st.markdown('<div class="dh-section-label">Recent Documents</div>', unsafe_allow_html=True)
    tab_recent, tab_dl, tab_modified = st.tabs(["Recently Generated", "Most Downloaded", "Last Modified"])
    display_docs = [{k: v for k, v in d.items() if not k.startswith("_")} for d in docs]
    with tab_recent:
        recent = display_docs[-5:][::-1]
        if recent:
            st.dataframe(_safe_df(pd.DataFrame(recent)), hide_index=True, use_container_width=True)
        else:
            st.caption("No documents generated yet.")
    with tab_dl:
        dl_counts = st.session_state.get("_doc_dl_counts", {})
        dl_docs = sorted(display_docs, key=lambda d: dl_counts.get(d.get("Document Name", ""), 0), reverse=True)[:5]
        rows = [{**d, "Downloads": dl_counts.get(d.get("Document Name", ""), 0)} for d in dl_docs]
        if rows:
            st.dataframe(_safe_df(pd.DataFrame(rows)), hide_index=True, use_container_width=True)
        else:
            st.caption("No download history yet.")
    with tab_modified:
        modified = sorted(display_docs, key=lambda d: d.get("Generated Date", ""), reverse=True)[:5]
        if modified:
            st.dataframe(_safe_df(pd.DataFrame(modified)), hide_index=True, use_container_width=True)
        else:
            st.caption("No documents found.")


def _render_overview(docs: list[dict]) -> None:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        empty_state_card(
            "No repository loaded",
            "Upload your Talend ZIP on the Home page and run analysis to populate documents.",
            "warning",
        )
        return

    _render_quick_actions()
    st.divider()
    st.markdown('<div class="dh-section-label">Generation Status</div>', unsafe_allow_html=True)
    _render_generation_tracker()
    st.divider()
    _render_recent_documents(docs)
    st.divider()
    st.markdown('<div class="dh-section-label">Document Categories</div>', unsafe_allow_html=True)
    for cat, doc_types in _CATEGORIES.items():
        cat_docs = [d for d in docs if d["Category"] == cat]
        with st.expander(f"**{cat}** — {len(cat_docs)} document(s)", expanded=len(cat_docs) > 0):
            if cat_docs:
                st.dataframe(_safe_df(pd.DataFrame(
                    [{k: v for k, v in d.items() if not k.startswith("_")} for d in cat_docs]
                )), hide_index=True, use_container_width=True)
            else:
                st.caption(f"No {cat} documents available yet.")


# ── Section: Search ───────────────────────────────────────────────────────────

def _render_search_section(docs: list[dict]) -> None:
    st.markdown("### 🔍 Document Search")
    query = st.text_input("Search documents…", key="doc_search_query",
                          placeholder="Type document name, type, or repository…")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        type_opts = ["All"] + sorted({d["Document Type"] for d in docs})
        sel_type = st.selectbox("Document Type", type_opts, key="doc_filter_type")
    with fc2:
        date_opts = ["All", "Today", "Last 7 days", "Last 30 days"]
        sel_date = st.selectbox("Date", date_opts, key="doc_filter_date")
    with fc3:
        repo_opts = ["All"] + sorted({d["Repository"] for d in docs if d["Repository"] != "—"})
        if len(repo_opts) <= 1:
            repo_opts = ["All", st.session_state.get("last_repo_name", "—")]
        sel_repo = st.selectbox("Repository", repo_opts, key="doc_filter_repo")
    with fc4:
        sel_status = st.selectbox("Status", ["All", "Available", "Pending"], key="doc_filter_status")

    filtered = docs[:]
    if query:
        q = query.lower()
        filtered = [d for d in filtered if q in d.get("Document Name", "").lower()
                    or q in d.get("Document Type", "").lower()
                    or q in d.get("Repository", "").lower()]
    if sel_type != "All":
        filtered = [d for d in filtered if d["Document Type"] == sel_type]
    if sel_date != "All":
        now_s  = datetime.now()
        cutoff = (now_s - timedelta(days={"Today": 0, "Last 7 days": 7, "Last 30 days": 30}.get(sel_date, 0))).strftime("%Y-%m-%d")
        filtered = [d for d in filtered if d.get("Generated Date", "") >= cutoff]
    if sel_repo != "All":
        filtered = [d for d in filtered if d.get("Repository") == sel_repo]
    if sel_status != "All":
        filtered = [d for d in filtered if d.get("Status") == sel_status]

    st.caption(f"Found **{len(filtered)}** of {len(docs)} document(s)")
    if not filtered:
        empty_state_card("No documents match", "Try adjusting your filters.", "info")
        return

    display_rows = [{k: v for k, v in d.items() if not k.startswith("_")} for d in filtered]
    st.dataframe(_safe_df(pd.DataFrame(display_rows)), hide_index=True, use_container_width=True)

    sel_preview = st.selectbox("Select document to preview:", ["—"] + [d["Document Name"] for d in filtered],
                               key="doc_search_preview_sel")
    if sel_preview != "—":
        sel_doc = next((d for d in filtered if d["Document Name"] == sel_preview), None)
        if sel_doc:
            _render_document_preview(sel_doc)


# ── Section renderers (preserved APIs) ───────────────────────────────────────

def _render_tdd_download_all_sections() -> None:
    """Download TDD exports for ALL jobs at once as a ZIP bundle."""
    import io
    import zipfile
    from app.tiap.documentation.tdd_export import export_tdd, _safe_job_name

    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        st.caption("No jobs loaded — run analysis first.")
        return

    st.markdown("**Download All Sections**")
    st.caption(f"Generate and bundle TDD exports for all {len(jobs)} job(s) into a ZIP archive.")

    fmt_options = ["Markdown (.md)", "HTML (.html)", "Word (.docx)", "PDF (.pdf)"]
    fmt_keys    = ["markdown", "html", "docx", "pdf"]
    selected_fmts = st.multiselect(
        "Select export formats", fmt_options, default=fmt_options,
        key="tdd_all_fmt_sel",
    )

    if st.button("⬇️  Generate & Download All", key="tdd_dl_all_btn", use_container_width=True):
        selected_keys = [fmt_keys[fmt_options.index(f)] for f in selected_fmts]
        zip_buffer = io.BytesIO()
        with st.spinner(f"Generating TDD exports for {len(jobs)} job(s)…"):
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for job_wrap in jobs:
                    jd = job_wrap.get("job_data", {})
                    job_name = jd.get("job_name", "Unknown")
                    try:
                        out_dir = os.path.join("/tmp", "tma_tdd_exports_all", _safe_job_name(job_name))
                        paths = export_tdd(jd, out_dir)
                        for fmt_key, path in paths.items():
                            if fmt_key in selected_keys and os.path.exists(path):
                                arcname = f"{_safe_job_name(job_name)}/{os.path.basename(path)}"
                                zf.write(path, arcname)
                    except Exception as exc:
                        # Write an error note for this job
                        zf.writestr(f"{_safe_job_name(job_name)}/ERROR.txt", str(exc))
        zip_buffer.seek(0)
        st.download_button(
            "📦  Download ZIP Bundle",
            data=zip_buffer.getvalue(),
            file_name="TDD_All_Jobs.zip",
            mime="application/zip",
            key="tdd_all_dl_zip",
            use_container_width=True,
        )


def _render_tdd_section() -> None:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        empty_state_card("No repository loaded", "Upload and analyse a Talend repository first.", "warning")
        return
    # Embed full TDD page inline (merged — no separate navigation needed)
    from app.ui.tdd_page import (
        _SECTIONS, _render_executive_summary, _render_architecture,
        _render_source_architecture, _render_target_architecture,
        _render_mapping, _render_transformation_architecture,
        _render_job_flow_architecture, _render_column_lineage_tdd,
        _render_validation, _render_error_handling, _render_audit_monitoring,
        _render_performance, _render_security, _render_dependency_architecture,
        _render_testing_section, _render_migration_assessment_section,
        _render_ai_summary_section, _render_tdd_download_section,
    )
    col_l, col_r1, col_r2 = st.columns([5, 1.5, 1.5])
    with col_l:
        st.caption("Per-job TDD with full architecture, source/target mapping, column lineage, and AI descriptions.")
    with col_r1:
        _tdd_export_popover = st.popover("⬇️  Download TDD", use_container_width=True)
        with _tdd_export_popover:
            _render_tdd_download_section(_key_suffix="_dh")
    with col_r2:
        _tdd_all_popover = st.popover("📦  Download All", use_container_width=True)
        with _tdd_all_popover:
            _render_tdd_download_all_sections()

    st.divider()

    section_labels = [f"{icon} {name}" for icon, name, _ in _SECTIONS]
    selected_label = st.selectbox(
        "Select Section", section_labels,
        index=st.session_state.get("dh_tdd_section_idx", 0),
        key="dh_tdd_section_nav",
    )
    selected_idx = section_labels.index(selected_label)
    st.session_state["dh_tdd_section_idx"] = selected_idx

    st.divider()

    icon, name, desc = _SECTIONS[selected_idx]
    label_html = (
        f'<div style="border-left:4px solid #6366f1;padding:6px 0 4px 14px;margin-bottom:10px;">' +
        f'<span style="font-size:20px">{icon}</span> ' +
        f'<span style="font-size:17px;font-weight:700;color:#0f172a">{name}</span>' +
        (f'<br><span style="font-size:12px;color:#64748b">{desc}</span>' if desc else '') +
        '</div>'
    )
    st.markdown(label_html, unsafe_allow_html=True)

    _RENDERERS = [
        _render_executive_summary, _render_architecture,
        _render_source_architecture, _render_target_architecture,
        _render_mapping, _render_transformation_architecture,
        _render_job_flow_architecture, _render_column_lineage_tdd,
        _render_validation, _render_error_handling, _render_audit_monitoring,
        _render_performance, _render_security, _render_dependency_architecture,
        _render_testing_section, _render_migration_assessment_section,
        _render_ai_summary_section,

    ]
    _RENDERERS[selected_idx]()


def _render_lld_section() -> None:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        empty_state_card("No repository loaded", "Upload and analyse a Talend repository first.", "warning")
        return
    st.markdown("#### Low-Level Design — Component & Column Mapping")
    st.caption("Detailed component mapping, column-level data lineage, tMap transformation logic.")
    from app.ui.column_mapping_page import render_column_mapping_tab
    job_names = [j.get("job_data", {}).get("job_name", f"Job {i}") for i, j in enumerate(jobs)]
    sel = st.selectbox("Select Job for LLD", job_names, key="lld_job_sel")
    idx = job_names.index(sel) if sel in job_names else 0
    job = jobs[idx]
    jd  = job.get("job_data", {})
    inv = job.get("inventory", {})
    render_column_mapping_tab(job=job, jd=jd, inv=inv, all_jobs=jobs, job_name=sel)


def _render_runbooks_section() -> None:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        empty_state_card("No repository loaded", "Upload and analyse a Talend repository first.", "warning")
        return
    st.markdown("#### Migration Runbook")
    st.caption("Step-by-step migration phases, waves, dependencies, risks, milestones, and validation tasks.")
    from app.ui.migration_runbook_dashboard import (
        build_migration_runbook, render_migration_runbook_dashboard,
    )
    runbook = st.session_state.get("migration_runbook")
    if runbook is None:
        if st.button("Generate Migration Runbook", type="primary", use_container_width=True, key="dh_gen_runbook"):
            with st.spinner("Building runbook…"):
                try:
                    runbook = build_migration_runbook(jobs, st.session_state.get("upgrade_advisor"))
                    st.session_state["migration_runbook"] = runbook
                    st.session_state.pop("_gen_fail_Migration Runbook", None)
                except Exception as e:
                    st.session_state["_gen_fail_Migration Runbook"] = str(e)
                    st.error(f"Generation failed: {e}")
            st.rerun()
        return
    render_migration_runbook_dashboard(runbook=runbook)


def _render_architecture_section() -> None:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        empty_state_card("No repository loaded", "Upload and analyse a Talend repository first.", "warning")
        return
    st.markdown("#### Architecture Intelligence")
    st.caption("Anti-pattern detection, architecture scorecard, best practices, technical debt, and autofix intelligence.")
    from app.ui.architecture_intelligence_dashboard import (
        build_architecture_autofix_intelligence,
        render_architecture_intelligence_dashboard,
    )
    data = st.session_state.get("architecture_autofix_intelligence")
    if data is None:
        if st.button("Generate Architecture Report", type="primary", use_container_width=True, key="dh_gen_arch"):
            with st.spinner("Analysing architecture…"):
                try:
                    data = build_architecture_autofix_intelligence(
                        jobs,
                        readiness=st.session_state.get("readiness_score", {}),
                        migration_intelligence=st.session_state.get("migration_intelligence"),
                        impact_intelligence=st.session_state.get("impact_intelligence"),
                    )
                    st.session_state["architecture_autofix_intelligence"] = data
                    st.session_state.pop("_gen_fail_Architecture Report", None)
                except Exception as e:
                    st.session_state["_gen_fail_Architecture Report"] = str(e)
                    st.error(f"Generation failed: {e}")
            st.rerun()
        return
    render_architecture_intelligence_dashboard(data=data)


def _render_reports_section() -> None:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        empty_state_card("No repository loaded", "Upload and analyse a Talend repository first.", "warning")
        return
    st.markdown("#### Reports")
    tabs = st.tabs(["Executive Reports", "Migration Reports"])
    with tabs[0]:
        st.caption("Executive-level cost, timeline, resource, KPI, roadmap, and summary reports.")
        from app.ui.dashboard import render_executive_reports_pack
        from app.ui.executive_dashboard_page import build_executive_dashboard_model
        model = st.session_state.get("executive_dashboard_model") or build_executive_dashboard_model()
        if model is None:
            st.info("Run repository analysis first to generate executive reports.")
        else:
            render_executive_reports_pack(model, jobs, st.session_state.get("effort_estimate", {}))
    with tabs[1]:
        st.caption("Migration intelligence, impact intelligence, and analysis reports.")
        r_tabs = st.tabs(["Migration Intelligence", "Impact Intelligence"])
        with r_tabs[0]:
            from app.ui.migration_intelligence_dashboard import (
                build_migration_intelligence, render_migration_intelligence_dashboard,
            )
            data = st.session_state.get("migration_intelligence")
            if data is None:
                if st.button("Generate Migration Intelligence Report", type="primary",
                             use_container_width=True, key="dh_gen_mi"):
                    with st.spinner("Generating…"):
                        try:
                            data = build_migration_intelligence(jobs, st.session_state.get("readiness_score", {}))
                            st.session_state["migration_intelligence"] = data
                        except Exception as e:
                            st.error(f"Generation failed: {e}")
                    st.rerun()
            else:
                render_migration_intelligence_dashboard(data=data)
        with r_tabs[1]:
            from app.ui.impact_intelligence_dashboard import (
                build_impact_intelligence, render_impact_intelligence_dashboard,
            )
            data = st.session_state.get("impact_intelligence")
            if data is None:
                if st.button("Generate Impact Intelligence Report", type="primary",
                             use_container_width=True, key="dh_gen_ii"):
                    with st.spinner("Generating…"):
                        try:
                            data = build_impact_intelligence(
                                jobs,
                                migration_intelligence=st.session_state.get("migration_intelligence"),
                                readiness=st.session_state.get("readiness_score", {}),
                            )
                            st.session_state["impact_intelligence"] = data
                        except Exception as e:
                            st.error(f"Generation failed: {e}")
                    st.rerun()
            else:
                render_impact_intelligence_dashboard(data=data)


# ── Export Center (enterprise redesign) ───────────────────────────────────────

def _render_export_center() -> None:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        empty_state_card("No repository loaded", "Upload and analyse a Talend repository first.", "warning")
        return

    st.markdown('<div class="dh-section-label">Export Center</div>', unsafe_allow_html=True)

    # Export mode cards — matches Job 360 card style
    has_runbook = bool(st.session_state.get("migration_runbook"))
    has_arch    = bool(st.session_state.get("architecture_autofix_intelligence"))
    has_exec    = bool(st.session_state.get("executive_dashboard_model"))
    has_mi      = bool(st.session_state.get("migration_intelligence"))
    gen_count   = sum([bool(jobs), has_runbook, has_arch, has_exec, has_mi])

    export_mode_html = f"""
<div class="dh-export-grid">
  <div class="dh-export-card" style="border-top-color:#2563EB;">
    <div class="dh-export-card-icon">📄</div>
    <div class="dh-export-card-title">Current Document</div>
    <div class="dh-export-card-desc">Export the active document in your chosen format.</div>
    <div class="dh-export-card-meta">
      <span class="dh-pill dh-pill-ready">Available</span>
      <span style="font-size:11px;color:#64748b;">1 doc</span>
    </div>
  </div>
  <div class="dh-export-card" style="border-top-color:#16A34A;">
    <div class="dh-export-card-icon">📂</div>
    <div class="dh-export-card-title">Multiple Documents</div>
    <div class="dh-export-card-desc">Select and bundle several documents together.</div>
    <div class="dh-export-card-meta">
      <span class="dh-pill dh-pill-ready">{gen_count} ready</span>
      <span style="font-size:11px;color:#64748b;">{gen_count} docs</span>
    </div>
  </div>
  <div class="dh-export-card" style="border-top-color:#EA580C;">
    <div class="dh-export-card-icon">📦</div>
    <div class="dh-export-card-title">Complete Package</div>
    <div class="dh-export-card-desc">All documents, assets, images and diagrams in one ZIP.</div>
    <div class="dh-export-card-meta">
      <span class="dh-pill {'dh-pill-ready' if gen_count >= 3 else 'dh-pill-pending'}">{'Ready' if gen_count >= 3 else 'Pending'}</span>
      <span style="font-size:11px;color:#64748b;">ZIP archive</span>
    </div>
  </div>
  <div class="dh-export-card" style="border-top-color:#7C3AED;">
    <div class="dh-export-card-icon">🤖</div>
    <div class="dh-export-card-title">AI Report Pack</div>
    <div class="dh-export-card-desc">AI-generated DOCX/PDF/HTML assessment pack.</div>
    <div class="dh-export-card-meta">
      <span class="dh-pill dh-pill-ready">Available</span>
      <span style="font-size:11px;color:#64748b;">3 formats</span>
    </div>
  </div>
</div>
"""
    st.markdown(export_mode_html, unsafe_allow_html=True)

    # Export metrics row
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        metric_card("Documents", str(gen_count), f"{gen_count} of 7 generated", "blue")
    with mc2:
        metric_card("Export Formats", "4", "PDF · DOCX · HTML · ZIP", "purple")
    with mc3:
        est_pages = gen_count * 12
        metric_card("Est. Pages", str(est_pages), "Across all documents", "teal")
    with mc4:
        est_mb = round(gen_count * 0.4, 1)
        metric_card("Est. Size", f"{est_mb} MB", "Compressed ZIP package", "amber")

    st.divider()

    # New enterprise Export Center
    from app.ui.export_center import render_export_center
    render_export_center()

    st.divider()
    st.markdown("##### Legacy Export Tools")
    st.caption("Original Excel / JSON / Report-Pack tools. Kept for backward compatibility.")
    _render_legacy_export_tools(jobs)


def _render_legacy_export_tools(jobs: list) -> None:
    tabs = st.tabs(["PDF Exports", "Excel Exports", "JSON Exports", "Report Pack"])

    with tabs[0]:
        st.markdown("**PDF Downloads**")
        model = st.session_state.get("executive_dashboard_model")
        if model is None:
            st.info("Load Executive Reports first (Reports → Executive Reports) to enable PDF exports.")
        else:
            from app.ui.dashboard import (
                _exec_business_model, _exec_summary_df, _exec_cost_df,
                _exec_timeline_df, _exec_resource_df, _exec_roadmap_df,
            )
            readiness  = st.session_state.get("readiness_score", {})
            effort     = st.session_state.get("effort_estimate", {})
            routines   = st.session_state.get("routine_analysis", {})
            joblets    = st.session_state.get("joblet_analysis", {})
            deprecated = st.session_state.get("deprecated_rows", [])
            custom     = st.session_state.get("custom_analysis", {})
            m = _exec_business_model(jobs, readiness, effort, routines, joblets, deprecated, custom)
            c1, c2 = st.columns(2)
            with c1:
                pdf_download_button("Executive Summary",   [("Summary",   _exec_summary_df(m))],   "ec_exec_summary", "Executive_Summary.pdf")
                pdf_download_button("Cost Estimation",     [("Cost",      _exec_cost_df(m))],       "ec_cost",         "Executive_Cost.pdf")
                pdf_download_button("Timeline",            [("Timeline",  _exec_timeline_df(m))],   "ec_timeline",     "Executive_Timeline.pdf")
            with c2:
                pdf_download_button("Resource Planning",   [("Resources", _exec_resource_df(m))],   "ec_resources",    "Executive_Resources.pdf")
                pdf_download_button("Roadmap",             [("Roadmap",   _exec_roadmap_df(m))],    "ec_roadmap",      "Executive_Roadmap.pdf")

        arch_data = st.session_state.get("architecture_autofix_intelligence")
        if arch_data:
            st.divider()
            st.markdown("**Architecture Report PDF**")
            from app.ui.architecture_intelligence_dashboard import export_architecture_autofix
            pdf_bytes = export_architecture_autofix(arch_data, "pdf")
            if pdf_bytes:
                st.download_button("Architecture Report PDF", data=pdf_bytes,
                                   file_name="Architecture_Report.pdf",
                                   use_container_width=True, key="ec_arch_pdf")

        impact_data = st.session_state.get("impact_intelligence")
        if impact_data:
            st.divider()
            st.markdown("**Impact Intelligence PDF**")
            from app.ui.impact_intelligence_dashboard import export_impact_intelligence
            pdf_bytes = export_impact_intelligence(impact_data, "pdf")
            if pdf_bytes:
                st.download_button("Impact Intelligence PDF", data=pdf_bytes,
                                   file_name="Impact_Intelligence.pdf",
                                   use_container_width=True, key="ec_impact_pdf")

    with tabs[1]:
        st.markdown("**Excel Downloads**")
        if st.button("Generate Excel Report", type="primary", use_container_width=True, key="ec_gen_excel"):
            with st.spinner("Generating Excel…"):
                from app.reports.excel_report import export_excel
                rpt = export_excel(jobs)
                if rpt and os.path.exists(rpt):
                    with open(rpt, "rb") as f:
                        st.session_state["ec_excel_bytes"] = f.read()
                    st.success("Excel report generated.")
        excel_bytes = st.session_state.get("ec_excel_bytes")
        if not excel_bytes and st.session_state.get("wizard_report_file"):
            fp = st.session_state.get("wizard_report_file", "")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    excel_bytes = f.read()
        if excel_bytes:
            st.download_button("Download Excel Report", data=excel_bytes,
                               file_name="Migration_Analysis.xlsx",
                               use_container_width=True, key="ec_dl_excel")

    with tabs[2]:
        st.markdown("**JSON Downloads**")
        runbook = st.session_state.get("migration_runbook")
        if runbook:
            from app.ui.migration_runbook_dashboard import export_runbook
            st.download_button("Runbook JSON", data=export_runbook(runbook, "json"),
                               file_name="migration_runbook.json",
                               use_container_width=True, key="ec_runbook_json")
        mi_data = st.session_state.get("migration_intelligence")
        if mi_data:
            from app.ui.migration_intelligence_dashboard import export_migration_intelligence
            st.download_button("Migration Intelligence JSON",
                               data=export_migration_intelligence(mi_data, "json"),
                               file_name="migration_intelligence.json",
                               use_container_width=True, key="ec_mi_json")
        arch_data = st.session_state.get("architecture_autofix_intelligence")
        if arch_data:
            from app.ui.architecture_intelligence_dashboard import export_architecture_autofix
            st.download_button("Architecture Report JSON",
                               data=export_architecture_autofix(arch_data, "json"),
                               file_name="architecture_report.json",
                               use_container_width=True, key="ec_arch_json")
        if not any([runbook, mi_data, arch_data]):
            st.info("Generate reports in the Reports and Architecture sections to enable JSON exports.")

    with tabs[3]:
        st.markdown("**Complete Assessment Report Pack**")
        st.caption("AI-generated DOCX/PDF/HTML report pack covering the full repository assessment.")
        from app.tiap.documentation.report_pack_generator import (
            REPORT_PACK_FILENAME, REPORT_PACK_SESSION_KEY, build_report_pack,
        )
        from app.ai.repository_ai_context import REPOSITORY_AI_CONTEXT_SESSION_KEY
        from app.tiap.documentation.template_manager import (
            DEFAULT_TEMPLATE_PATH, TEMPLATE_SESSION_KEY,
            active_template_label, restore_default_template, save_custom_template,
        )
        if TEMPLATE_SESSION_KEY not in st.session_state:
            st.session_state[TEMPLATE_SESSION_KEY] = DEFAULT_TEMPLATE_PATH
        active_template = st.session_state[TEMPLATE_SESSION_KEY]

        tc1, tc2 = st.columns(2)
        with tc1:
            if st.button("Use Default Template", use_container_width=True, key="ec_tmpl_default"):
                st.session_state[TEMPLATE_SESSION_KEY] = DEFAULT_TEMPLATE_PATH
                active_template = DEFAULT_TEMPLATE_PATH
        with tc2:
            if st.button("Restore Default Template", use_container_width=True, key="ec_tmpl_restore"):
                st.session_state[TEMPLATE_SESSION_KEY] = restore_default_template()
                active_template = st.session_state[TEMPLATE_SESSION_KEY]
        st.caption(f"Active: {active_template_label(active_template)}")

        uploaded_tmpl = st.file_uploader("Upload Custom Template (.docx)", type=["docx"], key="ec_custom_tmpl")
        if uploaded_tmpl:
            active_template = save_custom_template(uploaded_tmpl)
            st.session_state[TEMPLATE_SESSION_KEY] = active_template

        generated_pack = st.session_state.get(REPORT_PACK_SESSION_KEY)
        if st.button("Generate AI Report Pack", type="primary", use_container_width=True, key="ec_gen_pack"):
            with st.spinner("Generating complete report pack…"):
                effort = st.session_state.get("effort_estimate", {})
                generated_pack = build_report_pack(
                    all_jobs=jobs,
                    repository_path=st.session_state.get("last_repo_path"),
                    output_dir="output",
                    effort=effort,
                    auto_fix_recs=st.session_state.get("auto_fix_recs"),
                    technical_template=st.session_state.get("technical_doc_template"),
                    report_template_path=active_template,
                    test_cases=None,
                    repository_ai_context=st.session_state.get(REPOSITORY_AI_CONTEXT_SESSION_KEY),
                )
                st.session_state[REPORT_PACK_SESSION_KEY] = generated_pack
                for key_s, fp in [
                    ("_rp_docx_bytes", generated_pack.get("docx_path")),
                    ("_rp_pdf_bytes",  generated_pack.get("pdf_path")),
                    ("_rp_html_bytes", generated_pack.get("html_path")),
                ]:
                    if fp and os.path.exists(fp):
                        with open(fp, "rb") as f:
                            st.session_state[key_s] = f.read()
            st.success(f"Generated {REPORT_PACK_FILENAME}")

        if generated_pack:
            d1, d2, d3 = st.columns(3)
            for col, label, key_s, fname, mime in [
                (d1, "Download DOCX", "_rp_docx_bytes", REPORT_PACK_FILENAME,
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                (d2, "Download PDF",  "_rp_pdf_bytes",  "Complete_Assessment.pdf", "application/pdf"),
                (d3, "Download HTML", "_rp_html_bytes", "Complete_Assessment.html", "text/html"),
            ]:
                with col:
                    data = st.session_state.get(key_s)
                    if data:
                        st.download_button(label, data=data, file_name=fname, mime=mime, use_container_width=True)
                    else:
                        st.button(label, disabled=True, use_container_width=True)


# ── Sticky Bottom Toolbar ─────────────────────────────────────────────────────

def _render_sticky_toolbar(current_section: str) -> None:
    sections_order = ["tdd"] + [c[2] for c in _DOC_CARDS if c[2] != "tdd"] + ["exports"]
    # Deduplicate while preserving order
    seen = set()
    sections_order = [x for x in sections_order if not (x in seen or seen.add(x))]
    idx = sections_order.index(current_section) if current_section in sections_order else 0

    st.markdown('<div class="dh-toolbar">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 4])
    with c1:
        if st.button("◀ Prev", key="dh_tb_prev", use_container_width=True,
                     disabled=idx <= 0):
            st.session_state["doc_hub_section"] = sections_order[idx - 1]; st.rerun()
    with c2:
        if st.button("Next ▶", key="dh_tb_next", use_container_width=True,
                     disabled=idx >= len(sections_order) - 1):
            st.session_state["doc_hub_section"] = sections_order[idx + 1]; st.rerun()
    with c3:
        if st.button("⬇ Export", key="dh_tb_export", type="primary", use_container_width=True):
            st.session_state["doc_hub_section"] = "exports"; st.rerun()
    with c4:
        if st.button("📄 TDD", key="dh_tb_home", use_container_width=True):
            st.session_state["doc_hub_section"] = "tdd"; st.rerun()
    with c5:
        curr_name = current_section.capitalize()
        total_docs = len(_build_document_registry())
        st.caption(f"📚 **{curr_name}** · {total_docs} documents available · Use tabs or sidebar to navigate.")
    st.markdown('</div>', unsafe_allow_html=True)


# ── Page Entry Point ──────────────────────────────────────────────────────────

def render_documentation_hub_page() -> None:
    _inject_css()

    # ── Header (matches Job 360 style) ────────────────────────────────────────
    st.markdown(
        '<div class="dh-header">'
        '<div class="dh-header-icon">📚</div>'
        '<div>'
        '<div class="dh-header-title">Documentation Hub</div>'
        '<div class="dh-header-sub">Centralized document management and export center.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # ── Sidebar ───────────────────────────────────────────────────────────────
    section = _doc_sidebar()
    docs    = _build_document_registry()

    # ── KPI Cards (like Job 360 Executive Metrics) ────────────────────────────
    _render_kpi_cards(docs)

    # Tab bar removed — TDD is the only section

    # ── Phase Workflow Cards removed (Migration Phase Overview hidden) ─────────
    # _render_phase_workflow_cards(section)

    st.divider()

    # ── Main content area (TDD only; Overview and other sections removed) ─────
    if section == "tdd":
        _render_tdd_section()
    # elif section == "overview":      # removed — TDD is the default landing
    #     _render_overview(docs)
    # elif section == "search":        # hidden
    #     _render_search_section(docs)
    # elif section == "lld":           # hidden
    #     _render_lld_section()
    # elif section == "runbooks":      # hidden
    #     _render_runbooks_section()
    # elif section == "architecture":  # hidden
    #     _render_architecture_section()
    # elif section == "reports":       # hidden
    #     _render_reports_section()
    # elif section == "exports":       # hidden
    #     _render_export_center()

    # ── Sticky Bottom Toolbar ─────────────────────────────────────────────────
    _render_sticky_toolbar(section)
