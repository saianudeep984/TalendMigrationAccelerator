"""
Artha TMA — PHASE 1 UI REFACTOR
Enterprise dashboard shell:
  - Top navigation bar replaces sidebar navigation
  - Compact padding / reduced whitespace
  - page_header() used on each routed page
  - render_kpi_row() used for 4-column KPI layout where applicable
  - All backend logic, session state keys, and page content UNCHANGED
"""
import io
import json
import os
import shutil
import time
import uuid
import zipfile
import html
import xml.etree.ElementTree as ET

import streamlit as st

from app.analyzers.health_score import rag_from_score as _score_to_rag
from app.utils.zip_extractor import safe_extract

# Cloud readiness status display — color/emoji for the RED/AMBER/GREEN rag value
_RAG_HEX = {"RED": "#e07070", "AMBER": "#c9a84c", "GREEN": "#4fa87a"}
_RAG_EMOJI = {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢"}


def _cloud_status_label(cr: dict) -> str:
    """Render a job's cloud readiness as a colored status label (no numeric score)."""
    rag = (cr or {}).get("rag", "—")
    emoji = _RAG_EMOJI.get(rag, "")
    readiness = (cr or {}).get("readiness", "UNKNOWN")
    return f"{emoji} {rag} ({readiness})"


def _cloud_status_summary(jobs: list) -> str:
    """Summarize the dominant cloud readiness status across a list of jobs."""
    rags = [j.get("cloud_readiness", {}).get("rag", "—") for j in jobs]
    if not rags:
        return "—"
    dominant = max(set(rags), key=rags.count)
    emoji = _RAG_EMOJI.get(dominant, "")
    return f"{emoji} {dominant}"


_STATUS_BADGE_STYLES = {
    "GREEN": {"bg": "#eef7f2", "border": "#a8d5bb", "text": "#3d7a59"},
    "AMBER": {"bg": "#fef8ee", "border": "#e5d09a", "text": "#856940"},
    "RED":   {"bg": "#fdf4f4", "border": "#deb8b8", "text": "#906060"},
}


def _status_badge(status: str) -> str:
    status = str(status or "UNKNOWN").upper()
    style = _STATUS_BADGE_STYLES.get(
        status,
        {"bg": "#f8fafc", "border": "#dbe3ea", "text": "#475569"},
    )
    return (
        f'<span class="tma-status-badge" style="background:{style["bg"]};'
        f'border-color:{style["border"]};color:{style["text"]};">'
        f'{html.escape(status)}</span>'
    )


def _render_status_badge_row(items: list[tuple[str, str]]) -> None:
    cells = "".join(
        "<div class='tma-status-item'>"
        f"<span class='tma-status-label'>{html.escape(str(label))}</span>"
        f"{_status_badge(status)}"
        "</div>"
        for label, status in items
    )
    st.markdown(
        """
        <style>
        .tma-status-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px 14px;
            align-items: center;
            margin: 4px 0 12px;
        }
        .tma-status-item {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            min-width: 0;
        }
        .tma-status-label {
            color: #475569;
            font-size: 12px;
            font-weight: 700;
        }
        .tma-status-badge {
            display: inline-flex;
            align-items: center;
            border: 1px solid;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 800;
            line-height: 1;
            padding: 5px 10px;
        }
        </style>
        """ + f"<div class='tma-status-row'>{cells}</div>",
        unsafe_allow_html=True,
    )



def _apply_summary_overflow_fix() -> None:
    """Keep Summary-page text inside cards, markdown, and tables."""
    st.markdown(
        """
        <style>
        .st-key-review_summary_overflow,
        .st-key-review_summary_overflow *,
        .tma-summary-scope,
        .tma-summary-scope * {
            box-sizing: border-box;
            min-width: 0;
        }
        .st-key-review_summary_overflow,
        .st-key-review_summary_overflow p,
        .st-key-review_summary_overflow li,
        .st-key-review_summary_overflow div,
        .st-key-review_summary_overflow span,
        .tma-summary-scope,
        .tma-summary-scope p,
        .tma-summary-scope li,
        .tma-summary-scope div,
        .tma-summary-scope span {
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .st-key-review_summary_overflow div[data-testid="stMetric"],
        .tma-summary-scope div[data-testid="stMetric"] {
            height: auto !important;
            min-height: 70px !important;
            overflow: hidden !important;
        }
        .st-key-review_summary_overflow div[data-testid="stMetricLabel"],
        .st-key-review_summary_overflow div[data-testid="stMetricValue"],
        .st-key-review_summary_overflow div[data-testid="stMetricDelta"],
        .tma-summary-scope div[data-testid="stMetricLabel"],
        .tma-summary-scope div[data-testid="stMetricValue"],
        .tma-summary-scope div[data-testid="stMetricDelta"] {
            max-width: 100% !important;
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }
        .st-key-review_summary_overflow div[data-testid="stMetricValue"],
        .tma-summary-scope div[data-testid="stMetricValue"] {
            font-size: clamp(16px, 2.2vw, 21px) !important;
            line-height: 1.15 !important;
        }
        .st-key-review_summary_overflow [data-testid="stMarkdownContainer"],
        .st-key-review_summary_overflow [data-testid="stMarkdownContainer"] *,
        .tma-summary-scope [data-testid="stMarkdownContainer"],
        .tma-summary-scope [data-testid="stMarkdownContainer"] * {
            max-width: 100%;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .st-key-review_summary_overflow table,
        .st-key-review_summary_overflow th,
        .st-key-review_summary_overflow td,
        .tma-summary-scope table,
        .tma-summary-scope th,
        .tma-summary-scope td {
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _close_summary_overflow_fix() -> None:
    return None


def _render_repository_executive_summary(
    source_version: str,
    target_version: str,
    metrics: list[tuple[str, str]],
) -> None:
    """Render repository executive summary metrics with stable wrapping cards."""
    st.markdown(
        """
        <style>
        .st-key-repository_executive_summary,
        .st-key-repository_executive_summary * {
            box-sizing: border-box;
            min-width: 0;
        }
        .st-key-repository_executive_summary {
            margin: 4px 0 10px;
        }
        .st-key-repository_executive_summary [data-testid="stMarkdownContainer"],
        .st-key-repository_executive_summary [data-testid="stMarkdownContainer"] * {
            max-width: 100%;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .tma-exec-summary-source {
            color: #334155;
            font-size: 13px;
            line-height: 1.45;
            margin: 2px 0 10px;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .tma-exec-summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
            gap: 8px;
            align-items: stretch;
            margin: 4px 0 12px;
        }
        .tma-exec-summary-card {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-left: 3px solid #2563eb;
            border-radius: 8px;
            padding: 10px 12px;
            min-height: 84px;
            height: 100%;
            box-shadow: 0 1px 2px rgba(15, 23, 42, .05);
            overflow: hidden;
        }
        .tma-exec-summary-label {
            color: #64748b;
            font-size: 10px;
            font-weight: 800;
            line-height: 1.25;
            text-transform: uppercase;
            letter-spacing: 0;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .tma-exec-summary-value {
            color: #0f172a;
            font-size: clamp(16px, 2vw, 22px);
            font-weight: 800;
            line-height: 1.18;
            margin-top: 6px;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="repository_executive_summary"):
        st.markdown("### Repository Migration Report")
        st.markdown(
            "<div class='tma-exec-summary-source'>"
            f"<strong>Source:</strong> {html.escape(str(source_version))} &rarr; "
            f"<strong>Target:</strong> {html.escape(str(target_version))}"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("#### Executive Summary")
        cards = "".join(
            "<div class='tma-exec-summary-card'>"
            f"<div class='tma-exec-summary-label'>{html.escape(str(label))}</div>"
            f"<div class='tma-exec-summary-value'>{html.escape(str(value))}</div>"
            "</div>"
            for label, value in metrics
        )
        st.markdown(
            f"<div class='tma-exec-summary-grid'>{cards}</div>",
            unsafe_allow_html=True,
        )


def _cloud_rag(cr: dict) -> str:
    """Get RAG status from a cloud_readiness dict (supports RAG status fields)."""
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    return _score_to_rag(cr.get("score", 0))

from app.ui.design_system_v2 import (
    apply_wizard_theme,
    download_card,
    metric_card,
    page_header,
    page_title,
    panel_open,
    panel_close,
    render_kpi_row,
    render_topnav,
    section_header,
    sidebar_brand,         # kept for import compat (no-op in Phase 1)
    sidebar_status,        # kept for import compat (no-op in Phase 1)
    status_card,
    success_banner,
    topbar,                # kept for import compat
    wizard_progress,
)
from app.ui.design_system_v2 import (
    empty_state_card,
    styled_dataframe,
)
from app.ui.score_explainer import render_score_explainer
from app.ui.ux_enhancements import (
    render_home_landing,
    render_error_card,
    render_no_repo_card,
    render_session_restore_banner,
    mark_settings_saved,
    render_unsaved_settings_warning,
    ds_section_header,
    rag_pill,
    record_recent_project,
    render_analyze_new_repo_button,
)

# ── Core analysis imports ─────────────────────────────────────────────────────
from app.parser.repository_scanner import find_talend_jobs
from app.parser.talend_xml_parser import TalendJobParser
from app.cache.cache_manager import CacheManager as _CacheManager
_tma_cache = _CacheManager()
from app.parser.version_detector import detect_talend_version
from app.analyzers.complexity_analyzer import calculate_complexity
from app.analyzers.component_analyzer import analyze_components
from app.analyzers.deprecated_checker import analyze_component_risks
from app.analyzers.cloud_readiness import calculate_cloud_readiness
from app.ai.migration_recommender import (
    DEFAULT_MIGRATION_RECOMMENDATION_PROMPT,
    generate_migration_recommendation,
)
from app.reports.excel_report import export_excel
from app.dependency.dependency_analyzer import DependencyAnalyzer
from app.dependency.graph_builder import DependencyGraphBuilder
from app.dependency.dependency_exporter import export_dependency_summary
from app.estimators.migration_estimator import MigrationEstimator
from app.risk_engine.risk_analyzer import RiskAnalyzer
from app.analyzers.custom_component_analyzer import (
    DEFAULT_COMPONENT_RECOMMENDATION_PROMPT,
    analyze_custom_components,
)
from app.analyzers.deprecated_dashboard import build_deprecated_dashboard
from app.analyzers.readiness_scorer import calculate_readiness_score
from app.analyzers.effort_estimator import estimate_repository_effort
from app.analyzers.auto_fix_engine import generate_auto_fix_recommendations
from app.transformation.partial_transformer import PartialTransformer
from app.transformation.migration_patch_exporter import MigrationPatchExporter
from app.transformation.transformation_summary import TransformationSummary
from app.knowledge_engine.modernization_advisor import ModernizationAdvisor
from app.migration_assistant.migration_token_checker import MigrationTokenChecker
from app.migration_assistant.studio_import_guide import StudioImportGuide
from app.analyzers.readiness_scorer import MigrationReadiness
from app.api.healthcheck import check_prerequisites
from app.config.assessment_config_store import (
    DEFAULT_CONFIG as ASSESSMENT_DEFAULT_CONFIG,
    load_config as load_assessment_config,
    reset_defaults as reset_assessment_defaults,
    save_config as save_assessment_config,
)

# ── Streamlit page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Artha Talend — Migration Accelerator",
    layout="wide",
    page_icon="assets/artha_logo.png",
    initial_sidebar_state="collapsed",
)
apply_wizard_theme()

if "assessment_config" not in st.session_state:
    _project_key = st.session_state.get("last_repo_path")
    st.session_state["assessment_config"] = load_assessment_config(_project_key)

# ── PHASE 1B — Dependency Graph node click routing ────────────────────────────
# Clicking a job node in the Dependency Graph (Command Center) navigates here
# via ?open_job=<job_name>. Route to Job Analysis using existing selected_job state.
_qp_open_job = st.query_params.get("open_job")
if _qp_open_job:
    st.session_state["selected_job"] = _qp_open_job
    st.session_state["_nav_idx2"] = 4  # job_analysis
    st.session_state["_advanced_page"] = None
    st.query_params.clear()
    st.rerun()

# ── PHASE 1 UI REFACTOR — Top Navigation Bar ──────────────────────────────────
# render_topnav() replaces: sidebar_brand() + st.sidebar.radio() + sidebar_status()
# It returns the active full page label (e.g. "🏠  Home") and preserves
# st.session_state["_nav_idx2"] unchanged.
_sel = render_topnav()

# Reset home upload flag when user navigates to a different page
if _sel != "home":
    st.session_state.pop("_home_show_upload", None)

# Navigation — sidebar calls below are no-ops kept for safety;
# they will not render anything (sidebar is hidden via CSS).
_has_analysis = "last_analysis_jobs" in st.session_state
_job_count = len(st.session_state.get("last_analysis_jobs", []))
sidebar_brand()
sidebar_status(_has_analysis, _job_count)

# The sidebar expander is removed; advanced page state is preserved.
# Entry points are now inline buttons within the Settings page.
_adv = st.session_state.get("_advanced_page")

# ── Advanced page routing (unchanged priority logic) ──────────────────────────
if _adv == "ollama":
    page_header("🤖", "Ollama Settings", "Configure local LLM profiles for AI-assisted migration analysis.")
    from app.config.ollama_profile_store import OllamaProfileStore
    _ops = OllamaProfileStore()
    _all = _ops.load_all()
    _profile_names = list(_all["profiles"].keys())
    _active_name = _all.get("active", "default")
    c1, c2 = st.columns([2, 1])
    with c1:
        _chosen = st.selectbox("Profile", _profile_names,
            index=_profile_names.index(_active_name) if _active_name in _profile_names else 0,
            key="ollama_profile_sel")
    with c2:
        _new_name = st.text_input("New profile name", key="ollama_new_profile_name")
    _prof = _all["profiles"].get(_chosen, {})
    _model   = st.text_input("Model", value=_prof.get("model", "qwen2.5-coder:3b"), key="ollama_model")
    _temp    = st.slider("Temperature", 0.0, 1.0, float(_prof.get("temperature", 0.3)), 0.05, key="ollama_temp")
    _topp    = st.slider("Top P",       0.0, 1.0, float(_prof.get("top_p", 0.9)),       0.05, key="ollama_topp")
    _maxtok  = st.slider("Max Tokens",  256, 8192, int(_prof.get("max_tokens", 4096)),   256,  key="ollama_maxtok")
    _ctx     = st.slider("Context Length", 1024, 32768, int(_prof.get("context_length", 8192)), 1024, key="ollama_ctx")
    _sysp    = st.text_area("System Prompt", value=_prof.get("system_prompt", "You are a Talend migration expert."), height=100, key="ollama_sysprompt")
    _settings = {"model": _model, "temperature": _temp, "top_p": _topp,
                 "max_tokens": _maxtok, "context_length": _ctx, "system_prompt": _sysp}
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("💾 Save Profile", key="ollama_save"):
            name = _new_name if _new_name else _chosen
            _ops.save_profile(name, _settings); st.success(f"Saved '{name}'")
    with b2:
        if st.button("✅ Set Active", key="ollama_activate"):
            _ops.set_active(_chosen); st.success(f"Active: {_chosen}")
    with b3:
        if st.button("🗑 Delete", key="ollama_delete") and _chosen != "default":
            _ops.delete_profile(_chosen); st.success(f"Deleted '{_chosen}'")
    with b4:
        st.caption(f"Active: **{_all.get('active','default')}**")
    if st.button("✕ Close Ollama Settings", key="nav_adv_close_ollama"):
        st.session_state["_advanced_page"] = None
        st.rerun()
    st.stop()

if _adv == "prompts":
    page_header("🧩", "Prompt Library", "Customize the AI prompts used during analysis and documentation generation.")
    from app.config.prompt_store import PromptStore
    _ps = PromptStore()
    _categories = ["executive_summary", "technical_doc", "functional_doc", "kt_doc",
                   "migration_assessment", "test_cases", "recommendations",
                   "routine_assessment", "joblet_assessment", "java_risk"]
    _cat = st.selectbox("Category", _categories, key="prompt_lib_category")
    _current = _ps.get(_cat)
    _edited  = st.text_area("Prompt", value=_current, height=320, key=f"prompt_edit_{_cat}")
    pc1, pc2, pc3 = st.columns([1, 1, 4])
    with pc1:
        if st.button("💾 Save", key="prompt_save"):
            _ps.save(_cat, _edited); st.success("Saved.")
    with pc2:
        if st.button("↺ Reset to Default", key="prompt_reset"):
            _ps.reset(_cat); st.success("Reset to default.")
    if st.button("✕ Close Prompt Library", key="nav_adv_close_prompts"):
        st.session_state["_advanced_page"] = None
        st.rerun()
    st.stop()

if _adv == "templates":
    page_header("📄", "Template Manager", "Upload and manage branded DOCX report templates.")
    from app.template_engine.template_manager import TemplateManager as _TM
    _tm = _TM()
    _active_t = _tm.get_active_template()
    status_card("Active Template", f"{_active_t.name}", "info")
    st.markdown("#### Upload New Template")
    _upl = st.file_uploader("Upload .docx template", type=["docx"], key="template_upload_main")
    if _upl:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as _tmp:
            _tmp.write(_upl.read())
        _tm.upload_template(_tmp.name)
        st.success("Template uploaded.")
    tm1, tm2 = st.columns([1, 5])
    with tm1:
        if st.button("↺ Restore Default Template", key="restore_template"):
            _tm.restore_default(); st.success("Restored.")
    if st.button("✕ Close Template Manager", key="nav_adv_close_templates"):
        st.session_state["_advanced_page"] = None
        st.rerun()
    st.stop()

if _adv == "job_analysis":
    _sel_job = st.session_state.get("selected_job_for_analysis")
    page_header("🔍", "Job Analysis", f"Detailed analysis for: {_sel_job}")
    _all_jobs = st.session_state.get("last_analysis_jobs", [])
    _job = next((j for j in _all_jobs if j["job_data"]["job_name"] == _sel_job), None)
    if _job:
        jd = _job["job_data"]
        cr = _job["cloud_readiness"]
        st.markdown(f"**Job Name:** {jd['job_name']}")
        st.markdown(f"**Components:** {len(jd.get('components', []))}")
        st.markdown(f"**Cloud Status:** {_cloud_status_label(cr)}")
        st.markdown(f"**Complexity:** {_job.get('complexity', {}).get('level', '—')}")
        st.markdown("#### Components")
        st.json(jd.get("components", []))
        st.markdown("#### Risk Report")
        st.json(_job.get("enterprise_risk_report", []))
    else:
        st.warning("Job not found.")
    if st.button("✕ Close Job Analysis", key="nav_adv_close_job_analysis"):
        st.session_state["_advanced_page"] = None
        st.rerun()
    st.stop()

# ── Routing for non-wizard pages ───────────────────────────────────────────────

if _sel == "command_center":
    page_header("🚀", "Migration Command Center",
                "Deep-dive analysis, dependency graphs, risk heatmaps, and AI insights.")
    from app.ui.preflight_dashboard import (
        render_enterprise_factory,
        render_custom_component_analyzer,
        render_readiness_score,
        render_risk_heatmap,
        render_auto_fix_recommendations,
    )
    from app.ui.ai_intelligence_page import render_ai_intelligence_hub
    from app.ui.migration_assistant_page import render_migration_assistant


    if "last_analysis_jobs" not in st.session_state:
        render_no_repo_card("Command Center")
        st.stop()

    all_jobs        = st.session_state["last_analysis_jobs"]
    repo_path       = st.session_state.get("last_repo_path", "")
    custom_analysis = st.session_state.get("custom_analysis", {})
    deprecated_rows = st.session_state.get("deprecated_rows", [])
    readiness_score = st.session_state.get("readiness_score", {})
    effort_estimate = st.session_state.get("effort_estimate", {})
    auto_fix_recs   = st.session_state.get("auto_fix_recs", [])

    _cmd_readiness = readiness_score.get('overall', 'RED')
    _cmd_readiness_caption = {
        "GREEN": "Ready to migrate", "AMBER": "Needs review", "RED": "Remediation needed",
    }.get(_cmd_readiness, readiness_score.get("status", ""))
    _cmd_est_weeks = effort_estimate.get("estimated_weeks", "N/A")
    try:
        _cmd_est_weeks_display = f"~{max(1, round(float(_cmd_est_weeks) * 7))}d" if float(_cmd_est_weeks) < 1 else str(_cmd_est_weeks)
    except (TypeError, ValueError):
        _cmd_est_weeks_display = str(_cmd_est_weeks)

    render_kpi_row([
        {"label": "Jobs Loaded",  "value": str(len(all_jobs)),
         "caption": "In scope",   "color": "#1d4ed8"},
        {"label": "Readiness",    "value": _cmd_readiness,
         "caption": _cmd_readiness_caption, "color": "#5f8f72"},
        {"label": "High Risk",
         "value": str(sum(1 for j in all_jobs for r in j.get("enterprise_risk_report",[])
                          if r.get("risk") in ("HIGH","CRITICAL"))),
         "caption": "Findings",   "color": "#be123c"},
        {"label": "Est. Weeks",   "value": _cmd_est_weeks_display,
         "caption": "Delivery baseline", "color": "#6d28d9"},
    ])

    tab_analysis, tab_ai, tab_assistant, tab_qlik = st.tabs([
        "Analysis",
        "AI Intelligence",
        "Migration Assistant",
        "🔵 Talend Readiness",
    ])

    with tab_analysis:
        total_components = sum(len(j["job_data"].get("components", [])) for j in all_jobs)
        complexity_counts = {}
        for job in all_jobs:
            level = job.get("complexity", {}).get("level") or job.get("estimation", {}).get("complexity", "UNKNOWN")
            complexity_counts[level] = complexity_counts.get(level, 0) + 1
        risk_count = sum(
            1 for j in all_jobs for r in j.get("enterprise_risk_report", [])
            if r.get("risk") in ("HIGH", "CRITICAL")
        )
        cloud_blockers = sum(1 for j in all_jobs if j.get("cloud_readiness", {}).get("readiness") == "LOW")

        render_kpi_row([
            {"label": "Repository Jobs", "value": str(len(all_jobs)), "caption": "Analyzed jobs", "color": "#1d4ed8"},
            {"label": "Components", "value": str(total_components), "caption": "Runtime assets", "color": "#0f766e"},
            {"label": "High Complexity", "value": str(complexity_counts.get("HIGH", 0) + complexity_counts.get("CRITICAL", 0)), "caption": "Migration effort drivers", "color": "#b45309"},
            {"label": "Risk Findings", "value": str(risk_count), "caption": f"{cloud_blockers} cloud blockers", "color": "#be123c"},
        ])

        left, right = st.columns(2)
        with left:
            panel_open("Repository Analysis", "Portfolio, components, contexts, dependencies, scoring", height=560)
            render_enterprise_factory(
                all_jobs, custom_analysis, deprecated_rows,
                readiness_score, effort_estimate, auto_fix_recs,
            )
            panel_close()
        with right:
            panel_open("Risk & Readiness", "Complexity, readiness, and heatmap", height=560)
            risk_tab, readiness_tab = st.tabs(["Risk", "Readiness"])
            with risk_tab:
                render_risk_heatmap(all_jobs)
                with st.expander("🔍 Why these scores?", expanded=False):
                    for _ridx, _rj in enumerate(all_jobs):
                        with st.expander(_rj["job_data"]["job_name"], expanded=False):
                            render_score_explainer(_rj, key_suffix=f"_{_ridx}")
            with readiness_tab:
                render_readiness_score(readiness_score)
            panel_close()

        with st.expander("Diagnostics, JSON, logs, and raw analysis outputs", expanded=False):
            st.json({
                "readiness_score": readiness_score,
                "effort_estimate": effort_estimate,
                "custom_analysis": custom_analysis,
                "deprecated_rows": deprecated_rows,
            })

    with tab_ai:
        left, right = st.columns(2)
        with left:
            panel_open("AI Recommendations", "Flowcharts, documentation, test cases, and copilot", height=620)
            render_ai_intelligence_hub(all_jobs, repo_path=repo_path)
            panel_close()
        with right:
            panel_open("Modernization & Cloud Readiness", "Component modernization and cloud blockers", height=620)
            cloud_rags = [j.get("cloud_readiness", {}).get("rag", "—") for j in all_jobs]
            dominant_rag = max(set(cloud_rags), key=cloud_rags.count) if cloud_rags else "—"
            render_kpi_row([
                {"label": "Cloud Readiness", "value": f"{_RAG_EMOJI.get(dominant_rag, '')} {dominant_rag}", "color": _RAG_HEX.get(dominant_rag, "#0f766e")},
                {"label": "Custom Components", "value": str(custom_analysis.get("total_custom", 0)), "color": "#b45309"},
                {"label": "Deprecated", "value": str(sum(r.get("count", 0) for r in deprecated_rows)), "color": "#be123c"},
                {"label": "AI Context", "value": "Ready" if st.session_state.get("repository_ai_context") else "Pending", "color": "#6d28d9"},
            ])
            render_custom_component_analyzer(custom_analysis)
            with st.expander("Raw prompts and AI diagnostics", expanded=False):
                st.json(st.session_state.get("repository_ai_context", {}))
            panel_close()

    with tab_assistant:
        left, right = st.columns(2)
        with left:
            panel_open("Auto-Fix Suggestions", "Migration remediation candidates", height=600)
            render_auto_fix_recommendations(auto_fix_recs)
            panel_close()
        with right:
            panel_open("Migration Guidance", "Assistant workflow and generated outputs", height=600)
            render_migration_assistant()
            panel_close()

        with st.expander("Generated outputs, logs, and diagnostics", expanded=False):
            st.json({
                "wizard_report_file": st.session_state.get("wizard_report_file"),
                "wizard_patch_file": st.session_state.get("wizard_patch_file"),
                "last_repo_path": repo_path,
            })

    with tab_qlik:
        from app.ui.qlik_readiness_page import render_qlik_readiness_page
        panel_open("Talend Migration Readiness", "Native · Partial · Rewrite classification per job", height=620)
        render_qlik_readiness_page()
        panel_close()

    st.divider()
    render_analyze_new_repo_button(key="cmd_center_analyze_new", use_container_width=False)

    st.stop()

if _sel == "version_converter":
    from app.ui.version_converter_page import render_converter
    page_header("🔄", "Version Converter", "Upgrade or downgrade Talend job version mappings.")
    render_converter()
    st.stop()

if _sel == "executive_dashboard":
    try:
        from app.ui.executive_dashboard_page import render_executive_dashboard_page
    except ImportError as e:
        status_card(
            "Executive Dashboard unavailable",
            f"Failed to import dashboard module: {e}",
            "error",
        )
        st.stop()
    try:
        render_executive_dashboard_page()
    except Exception as e:
        status_card(
            "Executive Dashboard error",
            f"An error occurred while rendering the dashboard: {e}",
            "error",
        )
    st.divider()
    render_analyze_new_repo_button(key="exec_dash_analyze_new")
    st.stop()

if _sel == "portfolio":
    from app.ui.design_system_v2 import page_header
    page_header("📁", "Portfolio Dashboard", "Cross-repository migration portfolio overview — jobs, effort, risk, and status.")
    _pf_jobs = st.session_state.get("last_analysis_jobs", [])
    if not _pf_jobs:
        st.warning("Load a repository first to view portfolio metrics.")
    else:
        try:
            from app.ui.portfolio_dashboard import render_portfolio_dashboard
            render_portfolio_dashboard()
        except Exception as e:
            status_card("Portfolio Dashboard error", str(e), "error")
    st.divider()
    render_analyze_new_repo_button(key="portfolio_analyze_new")
    st.stop()

if _sel == "job_analysis":
    from app.ui.job_analysis_page import render_job_analysis_page
    render_job_analysis_page()
    st.divider()
    render_analyze_new_repo_button(key="job360_analyze_new")
    st.stop()

if _sel == "repository_search":
    from app.ui.repository_search_page import render_repository_search_page
    render_repository_search_page()
    st.divider()
    render_analyze_new_repo_button(key="repo_search_analyze_new")
    st.stop()

if _sel == "repo_lineage":
    from app.ui.repository_lineage_explorer_page import render_repository_lineage_explorer
    from app.ui.design_system_v2 import page_header
    page_header("🗺️", "Repository Lineage Explorer", "Cross-job data flow: Source → Job A → Job B → Job C → Target")
    render_repository_lineage_explorer()
    st.divider()
    render_analyze_new_repo_button(key="repo_lineage_analyze_new")
    st.stop()

# Documentation Hub and TDD are now merged into Job 360 Analysis (tabs: TDD, Docs Hub)
# Redirect old routes to job_analysis
if _sel in ("tdd", "documentation_hub"):
    st.session_state["_nav_idx2"] = next(
        (i for i, (k, _) in enumerate(__import__('app.ui.design_system_v2', fromlist=['_NAV_PAGES'])._NAV_PAGES) if k == "job_analysis"), 4
    )
    st.rerun()

if _sel == "testing_architecture":
    from app.ui.testing_architecture_page import render_testing_architecture_page
    from app.ui.design_system_v2 import page_header
    page_header("🧪", "Testing Architecture", "Unit Tests · Validation SQL · Reconciliation · Source vs Target")
    _ta_jobs = st.session_state.get("last_analysis_jobs", st.session_state.get("all_jobs", []))
    if not _ta_jobs:
        st.warning("Load a repository first.")
    else:
        _ta_sel = st.selectbox("Select Job", [j["job_data"].get("job_name", f"Job {i}") for i, j in enumerate(_ta_jobs)])
        _ta_wrap = next((j for j in _ta_jobs if j["job_data"].get("job_name") == _ta_sel), _ta_jobs[0])
        render_testing_architecture_page(_ta_wrap["job_data"])
    st.divider()
    render_analyze_new_repo_button(key="testing_arch_analyze_new")
    st.stop()

if _sel == "migration_assessment":
    from app.ui.migration_assessment_page import render_migration_assessment_page
    from app.ui.design_system_v2 import page_header
    page_header("🚀", "Migration Assessment", "Cloud Readiness · Unsupported Components · Risks · Effort · Recommendations")
    _ma_jobs = st.session_state.get("last_analysis_jobs", st.session_state.get("all_jobs", []))
    if not _ma_jobs:
        st.warning("Load a repository first.")
    else:
        _ma_sel = st.selectbox("Select Job", [j["job_data"].get("job_name", f"Job {i}") for i, j in enumerate(_ma_jobs)], key="ma_job_select")
        _ma_wrap = next((j for j in _ma_jobs if j["job_data"].get("job_name") == _ma_sel), _ma_jobs[0])
        render_migration_assessment_page(_ma_wrap["job_data"])
    st.divider()
    render_analyze_new_repo_button(key="migration_assess_analyze_new")
    st.stop()

if _sel == "exec_summary":
    from app.ui.exec_summary_page import render_exec_summary_page
    from app.ui.design_system_v2 import page_header
    page_header("🤖", "AI Executive Summary", "Business Summary · Technical Summary · Risks · Opportunities · Recommendations")
    _es_jobs = st.session_state.get("last_analysis_jobs", st.session_state.get("all_jobs", []))
    if not _es_jobs:
        st.warning("Load a repository first.")
    else:
        _es_sel = st.selectbox("Select Job", [j["job_data"].get("job_name", f"Job {i}") for i, j in enumerate(_es_jobs)], key="es_job_select")
        _es_wrap = next((j for j in _es_jobs if j["job_data"].get("job_name") == _es_sel), _es_jobs[0])
        render_exec_summary_page(_es_wrap["job_data"])
    st.divider()
    render_analyze_new_repo_button(key="exec_summary_analyze_new")
    st.stop()

if _sel == "settings":
    page_header("⚙️", "Assessment Configuration Hub", "Scoring rules, simulations, AI guidance, and governance.")
    import copy
    from app.parser.source_target_extractor import extract_sql_operations

    _sections = [
        "Assessment Rules", "Complexity Scoring", "Migration Risk", "Effort Estimation",
        "Cloud Readiness", "AI Recommendations", "Simulation Sandbox", "Import / Export",
    ]
    _requested = st.session_state.pop("settings_section", None)
    _default_idx = _sections.index(_requested) if _requested in _sections else 0
    _nav_col, _body_col = st.columns([1.2, 4])
    with _nav_col:
        _section = st.radio("Settings", _sections, index=_default_idx, key="assessment_settings_nav")

    _cfg = copy.deepcopy(st.session_state.get("assessment_config", ASSESSMENT_DEFAULT_CONFIG))
    _econ = _cfg.get("economics", ASSESSMENT_DEFAULT_CONFIG["economics"])
    st.session_state.setdefault("default_blended_rate", int(_econ.get("blended_daily_rate", 900)))
    st.session_state.setdefault("default_ai_reduction", int(_econ.get("ai_reduction_pct", 30)))
    _jobs = st.session_state.get("last_analysis_jobs", [])
    _selected_job = next((j for j in _jobs if j["job_data"].get("job_name") == st.session_state.get("selected_job")), _jobs[0] if _jobs else None)
    _jd = _selected_job.get("job_data", {}) if _selected_job else {"components": []}
    _components = len(_jd.get("components", []))
    _sql_count = len(extract_sql_operations(_jd.get("components", [])))
    _deps = len((_selected_job or {}).get("dependencies", {}).get("child_jobs", [])) if _selected_job else 0
    _custom = sum(1 for c in _jd.get("components", []) if "java" in str(c.get("component_type", "")).lower())
    _risk_findings = len((_selected_job or {}).get("enterprise_risk_report", [])) if _selected_job else 0

    def _rating(score, thresholds):
        if score <= thresholds["low"]:
            return "LOW"
        if score <= thresholds["medium"]:
            return "MEDIUM"
        if score <= thresholds["high"]:
            return "HIGH"
        return "CRITICAL"

    def _complexity_score(cfg):
        c = cfg["complexity"]
        return int(_components * c["component_weight"] + _sql_count * c["sql_weight"] + _deps * c["dependency_weight"] + _custom * c["custom_code_weight"] + _risk_findings * c["risk_weight"])

    def _risk_score(cfg):
        r = cfg["risk"]
        return int(_risk_findings * r["unsupported_components_penalty"] + _custom * r["custom_java_penalty"] + _deps * r["complex_dependency_penalty"])

    def _effort_hours(cfg):
        e = cfg["effort"]
        return round(_components * e["hours_per_component"] + _sql_count * e["hours_per_sql_query"] + _deps * e["hours_per_dependency"] + _custom * e["hours_per_custom_code"], 1)

    def _cloud_status(cfg):
        penalty = (_custom if cfg["cloud"]["custom_java_usage"] else 0) * 15 + (_risk_findings if cfg["cloud"]["unsupported_components"] else 0) * 12
        legacy_value = max(0, 100 - penalty)
        if legacy_value >= cfg["cloud"]["thresholds"]["ready"]:
            return "GREEN"
        if legacy_value >= cfg["cloud"]["thresholds"]["partially_ready"]:
            return "AMBER"
        return "RED"

    with _body_col:
        if _section == "Assessment Rules":
            st.markdown("### Assessment Rules")
            profiles = _cfg.get("profiles", ASSESSMENT_DEFAULT_CONFIG["profiles"])
            _cfg["active_profile"] = st.selectbox("Assessment Profile", profiles, index=profiles.index(_cfg.get("active_profile", "Enterprise")) if _cfg.get("active_profile") in profiles else 0)
            b1, b2, b3, b4 = st.columns(4)
            if b1.button("Create Profile", key="assess_create_profile"):
                profiles.append("Custom") if "Custom" not in profiles else None
                _cfg["active_profile"] = "Custom"
            if b2.button("Duplicate Profile", key="assess_duplicate_profile"):
                _cfg["active_profile"] = f"{_cfg['active_profile']} Copy"
                profiles.append(_cfg["active_profile"])
            if b3.button("Reset To Default", key="assess_reset_profile"):
                _cfg = copy.deepcopy(ASSESSMENT_DEFAULT_CONFIG)
            if b4.button("💾 Save Profile", type="primary", key="assess_save_profile"):
                st.session_state["assessment_config"] = _cfg
                save_assessment_config(_cfg, actor="settings")
                mark_settings_saved("Assessment Profile")
                # Clear per-section widget seeds so they reload from the saved config
                for _stale_key in ["cw_comp","cw_sql","cw_dep","cw_custom","cw_risk",
                                   "ct_low","ct_med","ct_high",
                                   "risk_unsupported","risk_java","risk_scripts","risk_legacy","risk_dep",
                                   "risk_thr_low","risk_thr_med","risk_thr_high",
                                   "eff_comp","eff_sql","eff_dep","eff_custom",
                                   "cloud_java","cloud_file","cloud_unsupported","cloud_context",
                                   "cloud_thr_ready","cloud_thr_partial"]:
                    st.session_state.pop(_stale_key, None)
                st.success("Profile saved and all sections refreshed.")
            _cfg["profiles"] = profiles
            st.json(_cfg)

        elif _section == "Complexity Scoring":
            c = _cfg["complexity"]
            st.markdown("### Complexity Weights")
            a, b, cc, d, e = st.columns(5)
            # Initialise session-state keys once so widgets keep their value across reruns
            st.session_state.setdefault("cw_comp",   int(c["component_weight"]))
            st.session_state.setdefault("cw_sql",    int(c["sql_weight"]))
            st.session_state.setdefault("cw_dep",    int(c["dependency_weight"]))
            st.session_state.setdefault("cw_custom", int(c["custom_code_weight"]))
            st.session_state.setdefault("cw_risk",   int(c["risk_weight"]))
            st.session_state.setdefault("ct_low",    int(c["thresholds"]["low"]))
            st.session_state.setdefault("ct_med",    int(c["thresholds"]["medium"]))
            st.session_state.setdefault("ct_high",   int(c["thresholds"]["high"]))
            a.number_input("Component Weight",  0, 500, key="cw_comp")
            b.number_input("SQL Weight",        0, 500, key="cw_sql")
            cc.number_input("Dependency Weight",0, 500, key="cw_dep")
            d.number_input("Custom Code Weight",0, 500, key="cw_custom")
            e.number_input("Risk Weight",       0, 500, key="cw_risk")
            # Read current widget values into cfg for live preview
            c["component_weight"]   = st.session_state["cw_comp"]
            c["sql_weight"]         = st.session_state["cw_sql"]
            c["dependency_weight"]  = st.session_state["cw_dep"]
            c["custom_code_weight"] = st.session_state["cw_custom"]
            c["risk_weight"]        = st.session_state["cw_risk"]
            st.markdown("### Complexity Thresholds")
            t1, t2, t3 = st.columns(3)
            t1.number_input("Low ceiling",    0, 1000, key="ct_low")
            t2.number_input("Medium ceiling", 0, 1000, key="ct_med")
            t3.number_input("High ceiling",   0, 1000, key="ct_high")
            c["thresholds"]["low"]    = st.session_state["ct_low"]
            c["thresholds"]["medium"] = st.session_state["ct_med"]
            c["thresholds"]["high"]   = st.session_state["ct_high"]
            score = _complexity_score(_cfg)
            _s1, _s2 = st.columns([3, 1])
            _s1.metric("Live Preview — Job Status", _rating(score, c["thresholds"]), f"Score: {score}")
            if _s2.button("💾 Save Changes", type="primary", key="save_complexity"):
                st.session_state["assessment_config"] = _cfg
                save_assessment_config(_cfg, actor="settings_complexity")
                mark_settings_saved("Complexity Scoring")

        elif _section == "Migration Risk":
            r = _cfg["risk"]
            st.markdown("### Migration Risk Penalties")
            cols = st.columns(5)
            st.session_state.setdefault("risk_unsupported", int(r["unsupported_components_penalty"]))
            st.session_state.setdefault("risk_java",        int(r["custom_java_penalty"]))
            st.session_state.setdefault("risk_scripts",     int(r["external_scripts_penalty"]))
            st.session_state.setdefault("risk_legacy",      int(r["legacy_components_penalty"]))
            st.session_state.setdefault("risk_dep",         int(r["complex_dependency_penalty"]))
            cols[0].number_input("Unsupported Components", 0, 200, key="risk_unsupported")
            cols[1].number_input("Custom Java",            0, 200, key="risk_java")
            cols[2].number_input("External Scripts",       0, 200, key="risk_scripts")
            cols[3].number_input("Legacy Components",      0, 200, key="risk_legacy")
            cols[4].number_input("Complex Dependencies",   0, 200, key="risk_dep")
            r["unsupported_components_penalty"] = st.session_state["risk_unsupported"]
            r["custom_java_penalty"]            = st.session_state["risk_java"]
            r["external_scripts_penalty"]       = st.session_state["risk_scripts"]
            r["legacy_components_penalty"]      = st.session_state["risk_legacy"]
            r["complex_dependency_penalty"]     = st.session_state["risk_dep"]
            st.markdown("**Risk Thresholds** — Low / Medium / High / Critical")
            _rt1, _rt2, _rt3 = st.columns(3)
            st.session_state.setdefault("risk_thr_low",  int(r["thresholds"]["low"]))
            st.session_state.setdefault("risk_thr_med",  int(r["thresholds"]["medium"]))
            st.session_state.setdefault("risk_thr_high", int(r["thresholds"]["high"]))
            _rt1.number_input("Low ceiling",    0, 500, key="risk_thr_low")
            _rt2.number_input("Medium ceiling", 0, 500, key="risk_thr_med")
            _rt3.number_input("High ceiling",   0, 500, key="risk_thr_high")
            r["thresholds"]["low"]    = st.session_state["risk_thr_low"]
            r["thresholds"]["medium"] = st.session_state["risk_thr_med"]
            r["thresholds"]["high"]   = st.session_state["risk_thr_high"]
            st.markdown("**HIGH/CRITICAL Finding Flags**")
            st.caption("Choose which component types are flagged as HIGH or CRITICAL risk findings.")
            _fc1, _fc2 = st.columns(2)
            st.session_state.setdefault("risk_flag_tjava",  bool(r.get("flag_tjava", True)))
            st.session_state.setdefault("risk_flag_depr",   bool(r.get("flag_deprecated", True)))
            st.session_state.setdefault("risk_flag_creds",  bool(r.get("flag_creds", True)))
            st.session_state.setdefault("risk_flag_ctx",    bool(r.get("flag_context", True)))
            _fc1.checkbox("🔴 Flag tJava / tJavaRow / tJavaFlex as HIGH", key="risk_flag_tjava")
            _fc1.checkbox("🔴 Flag deprecated components as HIGH",         key="risk_flag_depr")
            _fc2.checkbox("🔴 Flag hardcoded credentials as HIGH",         key="risk_flag_creds")
            _fc2.checkbox("🟡 Flag missing context groups as AMBER",       key="risk_flag_ctx")
            r["flag_tjava"]      = st.session_state["risk_flag_tjava"]
            r["flag_deprecated"] = st.session_state["risk_flag_depr"]
            r["flag_creds"]      = st.session_state["risk_flag_creds"]
            r["flag_context"]    = st.session_state["risk_flag_ctx"]
            _r1, _r2 = st.columns([3, 1])
            _r1.metric("Live Preview — Risk Rating", _rating(_risk_score(_cfg), r["thresholds"]), f"Score: {_risk_score(_cfg)}")
            if _r2.button("💾 Save Changes", type="primary", key="save_risk"):
                st.session_state["assessment_config"] = _cfg
                save_assessment_config(_cfg, actor="settings_risk")
                mark_settings_saved("Migration Risk")

        elif _section == "Effort Estimation":
            e = _cfg["effort"]
            st.markdown("### Effort Estimation")
            cols = st.columns(4)
            st.session_state.setdefault("eff_comp",   float(e["hours_per_component"]))
            st.session_state.setdefault("eff_sql",    float(e["hours_per_sql_query"]))
            st.session_state.setdefault("eff_dep",    float(e["hours_per_dependency"]))
            st.session_state.setdefault("eff_custom", float(e["hours_per_custom_code"]))
            cols[0].number_input("Hours / Component",   0.0, 50.0, step=0.1, format="%.2f", key="eff_comp")
            cols[1].number_input("Hours / SQL Query",   0.0, 50.0, step=0.1, format="%.2f", key="eff_sql")
            cols[2].number_input("Hours / Dependency",  0.0, 50.0, step=0.1, format="%.2f", key="eff_dep")
            cols[3].number_input("Hours / Custom Code", 0.0, 50.0, step=0.1, format="%.2f", key="eff_custom")
            e["hours_per_component"]  = st.session_state["eff_comp"]
            e["hours_per_sql_query"]  = st.session_state["eff_sql"]
            e["hours_per_dependency"] = st.session_state["eff_dep"]
            e["hours_per_custom_code"]= st.session_state["eff_custom"]
            st.code("Estimated Hours = (Components × h/comp) + (SQL × h/sql) + (Deps × h/dep) + (Custom × h/custom)")
            _e1, _e2 = st.columns([3, 1])
            _e1.metric("Live Preview — Estimate", f"{_effort_hours(_cfg)} hrs",
                       f"{round(_effort_hours(_cfg)/8, 1)} days · {round(_effort_hours(_cfg)/40, 1)} weeks")
            if _e2.button("💾 Save Changes", type="primary", key="save_effort"):
                st.session_state["assessment_config"] = _cfg
                save_assessment_config(_cfg, actor="settings_effort")
                mark_settings_saved("Effort Estimation")

        elif _section == "Cloud Readiness":
            c = _cfg["cloud"]
            st.markdown("### Cloud Readiness — Risk Factors")
            st.caption("Toggle each factor that applies to your repository. Active factors reduce the cloud readiness score.")
            cols = st.columns(4)
            st.session_state.setdefault("cloud_java",        bool(c["custom_java_usage"]))
            st.session_state.setdefault("cloud_file",        bool(c["file_system_dependency"]))
            st.session_state.setdefault("cloud_unsupported", bool(c["unsupported_components"]))
            st.session_state.setdefault("cloud_context",     bool(c["legacy_context_variables"]))
            cols[0].toggle("Custom Java Usage",        key="cloud_java")
            cols[1].toggle("File System Dependency",   key="cloud_file")
            cols[2].toggle("Unsupported Components",   key="cloud_unsupported")
            cols[3].toggle("Legacy Context Variables", key="cloud_context")
            c["custom_java_usage"]        = st.session_state["cloud_java"]
            c["file_system_dependency"]   = st.session_state["cloud_file"]
            c["unsupported_components"]   = st.session_state["cloud_unsupported"]
            c["legacy_context_variables"] = st.session_state["cloud_context"]
            st.markdown("### Cloud Readiness Thresholds")
            _ctl1, _ctl2 = st.columns(2)
            st.session_state.setdefault("cloud_thr_ready",   int(c["thresholds"]["ready"]))
            st.session_state.setdefault("cloud_thr_partial", int(c["thresholds"]["partially_ready"]))
            _ctl1.number_input("GREEN (ready) threshold %",          0, 100, key="cloud_thr_ready")
            _ctl2.number_input("AMBER (partially ready) threshold %", 0, 100, key="cloud_thr_partial")
            c["thresholds"]["ready"]           = st.session_state["cloud_thr_ready"]
            c["thresholds"]["partially_ready"] = st.session_state["cloud_thr_partial"]
            _cl1, _cl2 = st.columns([3, 1])
            _cl1.metric("Live Preview — Cloud Status", _cloud_status(_cfg))
            if _cl2.button("💾 Save Changes", type="primary", key="save_cloud"):
                st.session_state["assessment_config"] = _cfg
                save_assessment_config(_cfg, actor="settings_cloud")
                mark_settings_saved("Cloud Readiness")

        elif _section == "AI Recommendations":
            st.markdown("### AI Recommendations")
            if st.button("Analyze Assessment Settings", type="primary", key="analyze_assessment_settings"):
                st.info("Current SQL Weight increases complexity classification.")
                st.markdown("**Recommendation:** Reduce SQL Weight from 40 to 25.")
                st.markdown("- Lower average complexity classification\n- Improved status accuracy\n- Reduced false-positive HIGH ratings")

        elif _section == "Simulation Sandbox":
            st.markdown("### Simulation Sandbox")
            old_score = _complexity_score(_cfg)
            sim = copy.deepcopy(_cfg)
            s = sim["complexity"]
            st.metric("Current Status", _rating(old_score, _cfg["complexity"]["thresholds"]))
            c1, c2, c3 = st.columns(3)
            s["sql_weight"] = c1.number_input("SQL Weight", 0, 500, int(s["sql_weight"]), key="sim_sql")
            s["custom_code_weight"] = c2.number_input("Custom Code Weight", 0, 500, int(s["custom_code_weight"]), key="sim_custom")
            s["dependency_weight"] = c3.number_input("Dependency Weight", 0, 500, int(s["dependency_weight"]), key="sim_dep")
            new_score = _complexity_score(sim)
            st.metric("Simulation Result", f"{_rating(new_score, s['thresholds'])}")
            st.write(f"Rating Change: {_rating(old_score, _cfg['complexity']['thresholds'])} -> {_rating(new_score, s['thresholds'])}")
            if st.button("Apply Changes", type="primary", key="apply_sim_changes"):
                _cfg["complexity"] = s
                st.success("Simulation changes staged. Save configuration to persist.")

            st.divider()
            st.markdown("### 💰 Estimated Savings Calculator")
            st.caption("Drives the Estimated Savings KPI on every dashboard. "
                       "Formula: (Estimated Days × Blended Daily Rate) × AI Reduction %. "
                       "Changes here save automatically — no need to click Save.")
            sv1, sv2 = st.columns(2)
            sv1.number_input("Blended daily rate ($)", 100, 5000, step=50, key="default_blended_rate")
            sv2.slider("AI effort reduction (%)", 5, 60, key="default_ai_reduction")

            _live_days = (st.session_state.get("effort_estimate", {}) or {}).get("estimated_days", 0)
            _rate = st.session_state["default_blended_rate"]
            _redux = st.session_state["default_ai_reduction"]
            _base_cost = round(_live_days * _rate) if _live_days else 0
            _live_savings = round(_base_cost * _redux / 100)
            st.code(f"Estimated Savings = ({_live_days} days × ${_rate:,}/day) × {_redux}% = ${_live_savings:,}")

            # Auto-persist to disk the moment either widget changes, so the
            # value survives navigation, a browser refresh, or an app
            # restart — not just the current in-memory session.
            _econ_now = _cfg.get("economics", {})
            if _econ_now.get("blended_daily_rate") != _rate or _econ_now.get("ai_reduction_pct") != _redux:
                _cfg["economics"] = {"blended_daily_rate": _rate, "ai_reduction_pct": _redux}
                st.session_state["assessment_config"] = _cfg
                save_assessment_config(_cfg, actor="settings_economics_auto")

            sv3, sv4 = st.columns([3, 1])
            sv3.metric("Live Preview — Estimated Savings", f"${_live_savings:,}")
            if sv4.button("💾 Save Changes", type="primary", key="save_economics"):
                _cfg["economics"] = {
                    "blended_daily_rate": _rate,
                    "ai_reduction_pct": _redux,
                }
                st.session_state["assessment_config"] = _cfg
                save_assessment_config(_cfg, actor="settings_economics")
                mark_settings_saved("Simulation Sandbox")

            _on_disk_econ = load_assessment_config(None).get("economics", {})
            st.caption(
                f"📄 On disk right now: ${_on_disk_econ.get('blended_daily_rate', 900):,}/day, "
                f"{_on_disk_econ.get('ai_reduction_pct', 30)}% reduction "
                f"(file: config/assessment_config.json). If this doesn't match what you "
                f"just typed, the app process needs a restart to pick up the latest code."
            )

        elif _section == "Import / Export":
            st.markdown("### Import / Export")
            e1, e2, e3, e4 = st.columns(4)
            e1.download_button("Export Configuration", json.dumps(_cfg, indent=2), "assessment_config.json", "application/json")
            uploaded_cfg = e2.file_uploader("Import Configuration", type=["json"], label_visibility="collapsed")
            e3.download_button("Download Template", json.dumps(ASSESSMENT_DEFAULT_CONFIG, indent=2), "assessment_config_template.json", "application/json")
            if e4.button("Restore Defaults", key="restore_assessment_defaults"):
                _cfg = reset_assessment_defaults()
                st.success("Defaults restored.")
            if uploaded_cfg:
                _cfg = json.loads(uploaded_cfg.getvalue().decode("utf-8"))
                st.success("Configuration imported. Save to persist.")

    st.stop()

if False and _sel == "settings":
    page_header("⚙️", "Settings", "Configure migration defaults, display preferences, and advanced tools.")
    tab_general, tab_scoring, tab_ollama, tab_templates, tab_environment = st.tabs([
        "General",
        "Scoring",
        "Ollama",
        "Templates",
        "Environment",
    ])

    with tab_general:
        with st.form("settings_general_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.number_input("Blended daily rate ($)", 100, 5000, 900, 50, key="default_blended_rate")
            with c2:
                st.slider("AI effort reduction (%)", 5, 60, 30, key="default_ai_reduction")
            with c3:
                st.selectbox("Target platform", ["Talend 8", "Talend Cloud", "Hybrid"], key="default_target_platform")
            st.form_submit_button("Save General Settings", type="primary")
        with st.expander("Advanced display settings", expanded=False):
            st.toggle("Start in boardroom mode", True, key="settings_boardroom_default")
            st.toggle("Hide raw evidence by default", True, key="settings_hide_raw_default")

    with tab_scoring:
        # Allows users to view and edit the complexity scoring logic
        # (component weights, risk thresholds, and effort-hour mapping)
        # that drives Complexity / Migration Risk / Migration Effort /
        # Cloud Readiness across the app.
        import pandas as pd
        from app.analyzers import complexity_analyzer as _ca

        st.caption("These values drive Complexity, Migration Risk, Migration Effort and Cloud Readiness status shown across the app.")

        st.markdown("**Component Weights**")
        _weights_df = pd.DataFrame(
            [{"Component Type": k, "Weight": v} for k, v in _ca.WEIGHTS.items()]
        )
        _edited_weights = st.data_editor(
            _weights_df, hide_index=True, use_container_width=True,
            num_rows="dynamic", key="settings_scoring_weights_editor",
        )

        c1, c2 = st.columns(2)
        with c1:
            _default_weight = st.number_input(
                "Default weight (unlisted components)", 0, 100,
                int(_ca.DEFAULT_WEIGHT), 1, key="settings_scoring_default_weight",
            )
        with c2:
            st.caption("Used for any component type not listed above.")

        st.markdown("**Complexity Status Bands**")
        t1, t2, t3 = st.columns(3)
        with t1:
            _th_low = st.number_input("LOW max value", 0, 1000, int(_ca.THRESHOLDS["LOW"]), 5, key="settings_scoring_th_low")
        with t2:
            _th_medium = st.number_input("MEDIUM max value", 0, 1000, int(_ca.THRESHOLDS["MEDIUM"]), 5, key="settings_scoring_th_medium")
        with t3:
            _th_high = st.number_input("HIGH max value", 0, 1000, int(_ca.THRESHOLDS["HIGH"]), 5, key="settings_scoring_th_high")
        st.caption("Values at or above the HIGH max are classified CRITICAL.")

        st.markdown("**Migration Effort (hours)**")
        e1, e2 = st.columns(2)
        with e1:
            _effort_manual = st.number_input("Manual review effort (HIGH/CRITICAL)", 0, 200, int(_ca.EFFORT_HOURS["manual"]), 1, key="settings_scoring_effort_manual")
        with e2:
            _effort_auto = st.number_input("Auto-migratable effort (LOW/MEDIUM)", 0, 200, int(_ca.EFFORT_HOURS["auto"]), 1, key="settings_scoring_effort_auto")

        if st.button("Apply & Recalculate Status", type="primary", key="settings_scoring_apply"):
            _ca.WEIGHTS.clear()
            for _, _row in _edited_weights.iterrows():
                _ctype = str(_row.get("Component Type", "")).strip()
                if _ctype:
                    _ca.WEIGHTS[_ctype] = int(_row.get("Weight", _ca.DEFAULT_WEIGHT))
            _ca.DEFAULT_WEIGHT = int(_default_weight)
            _ca.THRESHOLDS["LOW"] = int(_th_low)
            _ca.THRESHOLDS["MEDIUM"] = int(_th_medium)
            _ca.THRESHOLDS["HIGH"] = int(_th_high)
            _ca.EFFORT_HOURS["manual"] = int(_effort_manual)
            _ca.EFFORT_HOURS["auto"] = int(_effort_auto)

            _jobs = st.session_state.get("last_analysis_jobs", [])
            for _job in _jobs:
                _job["complexity"] = _ca.calculate_complexity(_job["job_data"])
            st.session_state["last_analysis_jobs"] = _jobs
            # Invalidate the cached Repository Health Score so it is recomputed
            # from the updated complexity scores on the next consumer access.
            st.session_state.pop("repository_health_score", None)
            st.success(f"Scoring configuration applied and {len(_jobs)} job(s) recalculated.")


        from app.config.ollama_profile_store import OllamaProfileStore
        _ops = OllamaProfileStore()
        _all = _ops.load_all()
        _profile_names = list(_all["profiles"].keys())
        _active_name = _all.get("active", "default")
        with st.form("settings_ollama_form"):
            c1, c2 = st.columns([2, 1])
            with c1:
                _chosen = st.selectbox("Profile", _profile_names,
                    index=_profile_names.index(_active_name) if _active_name in _profile_names else 0,
                    key="settings_ollama_profile_sel")
            with c2:
                _new_name = st.text_input("New profile name", key="settings_ollama_new_profile_name")
            _prof = _all["profiles"].get(_chosen, {})
            c1, c2, c3 = st.columns(3)
            with c1:
                _model = st.text_input("Model", value=_prof.get("model", "qwen2.5-coder:3b"), key="settings_ollama_model")
            with c2:
                _temp = st.slider("Temperature", 0.0, 1.0, float(_prof.get("temperature", 0.3)), 0.05, key="settings_ollama_temp")
            with c3:
                _topp = st.slider("Top P", 0.0, 1.0, float(_prof.get("top_p", 0.9)), 0.05, key="settings_ollama_topp")
            c4, c5 = st.columns(2)
            with c4:
                _maxtok = st.slider("Max Tokens", 256, 8192, int(_prof.get("max_tokens", 4096)), 256, key="settings_ollama_maxtok")
            with c5:
                _ctx = st.slider("Context Length", 1024, 32768, int(_prof.get("context_length", 8192)), 1024, key="settings_ollama_ctx")
            with st.expander("Advanced system prompt", expanded=False):
                _sysp = st.text_area("System Prompt", value=_prof.get("system_prompt", "You are a Talend migration expert."), height=120, key="settings_ollama_sysprompt")
            _save = st.form_submit_button("Save Ollama Profile", type="primary")
        _settings = {"model": _model, "temperature": _temp, "top_p": _topp,
                     "max_tokens": _maxtok, "context_length": _ctx, "system_prompt": _sysp}
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if _save:
                name = _new_name if _new_name else _chosen
                _ops.save_profile(name, _settings); st.success(f"Saved '{name}'")
        with b2:
            if st.button("Set Active", key="settings_ollama_activate"):
                _ops.set_active(_chosen); st.success(f"Active: {_chosen}")
        with b3:
            if st.button("Delete", key="settings_ollama_delete") and _chosen != "default":
                _ops.delete_profile(_chosen); st.success(f"Deleted '{_chosen}'")
        with b4:
            st.caption(f"Active: **{_all.get('active','default')}**")

    with tab_templates:
        t1, t2 = st.columns(2)
        with t1:
            if st.button("Prompt Library", use_container_width=True, key="nav_prompts"):
                st.session_state["_advanced_page"] = "prompts"
                st.rerun()
        with t2:
            if st.button("Template Manager", use_container_width=True, key="nav_templates"):
                st.session_state["_advanced_page"] = "templates"
                st.rerun()
        with st.expander("Template diagnostics", expanded=False):
            st.write("Prompt and DOCX template tools open in focused edit views to preserve their existing save logic.")

    with tab_environment:
        _prereq = check_prerequisites()
        render_kpi_row([
            {"label": "Environment", "value": "Ready" if _prereq.get("ok") else "Needs Setup", "color": "#15803d" if _prereq.get("ok") else "#be123c"},
            {"label": "Ollama", "value": "Online" if _prereq.get("ollama_available") else "Offline", "color": "#15803d" if _prereq.get("ollama_available") else "#b45309"},
            {"label": "Errors", "value": str(len(_prereq.get("errors", []))), "color": "#be123c"},
            {"label": "Mode", "value": "Rule + AI" if _prereq.get("ollama_available") else "Rule-based", "color": "#1d4ed8"},
        ])
        with st.expander("Environment diagnostics", expanded=False):
            st.json(_prereq)
        with st.expander("Advanced tools", expanded=False):
            if st.button("Ollama Focus View", key="nav_ollama"):
                st.session_state["_advanced_page"] = "ollama"
                st.rerun()
    st.stop()

# ── WIZARD HOME ────────────────────────────────────────────────────────────────
# Determine current wizard step from session state (unchanged)

def _build_repository_report_zip(all_jobs, readiness_score, effort_estimate):
    """Build Repository Report ZIP: Executive Summary, Job Analysis Reports, Recommendations."""
    _total = len(all_jobs)
    _components = sum(len(j["job_data"].get("components", [])) for j in all_jobs)
    _high_risk = sum(
        1 for j in all_jobs for r in j.get("enterprise_risk_report", [])
        if r.get("risk") in ("HIGH", "CRITICAL")
    )
    _cloud_rags = [j.get("cloud_readiness", {}).get("rag", "—") for j in all_jobs]
    _cloud_status = max(set(_cloud_rags), key=_cloud_rags.count) if _cloud_rags else "—"
    _readiness = readiness_score.get("overall", "RED")
    _hs = st.session_state.get("repository_health_score") or {}
    _overall_status = _hs.get("overall_status") or _hs.get("risk_level") or "—"
    _health_score = _hs.get("overall_score") or _hs.get("health_score") or "—"
    _weeks = effort_estimate.get("estimated_weeks", "N/A") if effort_estimate else "N/A"
    _auto_pct = effort_estimate.get("auto_pct", 0) if effort_estimate else 0
    _complexity_counts = {}
    for _j in all_jobs:
        _lvl = _j.get("complexity", {}).get("level") or _j.get("estimation", {}).get("complexity", "UNKNOWN")
        _complexity_counts[_lvl] = _complexity_counts.get(_lvl, 0) + 1

    _zip_buf = io.BytesIO()
    with zipfile.ZipFile(_zip_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
        _exec_summary = f"""EXECUTIVE SUMMARY
=================
Source: {st.session_state.get('wizard_source_version', 'Unknown')} -> Target: {st.session_state.get('wizard_target_version_val', 'Talend 8')}

Total Jobs: {_total}
Total Components: {_components}
Migration Readiness: {_readiness}
Overall Status: {_overall_status}
Repository Health Score: {_health_score}/100
High/Critical Risk Findings: {_high_risk}
Estimated Delivery: {_weeks} weeks
Auto-Migratable: {_auto_pct}%

COMPLEXITY DISTRIBUTION
-----------------------
""" + "\n".join(f"{k}: {v} job(s)" for k, v in _complexity_counts.items())
        _zf.writestr("executive_summary/executive_summary.txt", _exec_summary)

        for _j in all_jobs:
            _jd = _j["job_data"]
            _jn = _jd["job_name"]
            _cr = _j["cloud_readiness"]
            _job_report = f"""JOB ANALYSIS REPORT — {_jn}
{'=' * (22 + len(_jn))}
Components: {len(_jd.get('components', []))}
Complexity: {_j.get('complexity', {}).get('level', '—')}
Cloud Status: {_cr.get('rag', '—')} ({_cr.get('readiness', 'UNKNOWN')})
Talend Version: {_jd.get('talend_version', '—')}
Job Version: {_jd.get('job_version', '—')}

RISK FINDINGS
-------------
""" + ("\n".join(
                f"[{r.get('risk','')}] {r.get('component','Unknown')}: {r.get('message','')}"
                for r in _j.get("enterprise_risk_report", [])
            ) or "None") + f"""

AI RECOMMENDATION
-----------------
{_j.get('ai_recommendation', 'N/A')}
"""
            _zf.writestr(f"job_analysis_reports/{_jn}.txt", _job_report)

        _auto_fix_recs = st.session_state.get("auto_fix_recs", [])
        _recommendations = "RECOMMENDATIONS\n===============\n\n"
        if _auto_fix_recs:
            for _rec in _auto_fix_recs:
                _recommendations += (
                    f"- [{_rec.get('severity', _rec.get('risk',''))}] "
                    f"{_rec.get('job_name', _rec.get('job',''))}: "
                    f"{_rec.get('recommendation', _rec.get('message',''))}\n"
                )
        else:
            _recommendations += "No automated recommendations available.\n"
        _recommendations += "\nMODERNIZATION NOTES\n-------------------\n"
        for _j in all_jobs:
            _mr = _j.get("modernization_report")
            if _mr:
                _recommendations += f"{_j['job_data']['job_name']}: {_mr}\n"
        _zf.writestr("recommendations/recommendations.txt", _recommendations)

    return _zip_buf.getvalue()

_step = st.session_state.get("wizard_step", 1)

# Home landing: show professional landing unless already in upload flow
if _sel == "home" and _step == 1 and "last_analysis_jobs" not in st.session_state and not st.session_state.get("_home_show_upload") and "wizard_uploaded_file_data" not in st.session_state:
    def _go_to_upload():
        # Used as a button on_click= callback: Streamlit guarantees this runs
        # and commits to session_state BEFORE the automatic rerun it triggers,
        # so no explicit st.rerun() is needed (or wanted) here.
        st.session_state["_home_show_upload"] = True
        st.session_state["_scroll_to_top_once"] = True
    render_home_landing(on_get_started=_go_to_upload)
    try:
        render_session_restore_banner(_tma_cache)
    except Exception:
        pass
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — REPOSITORY INTAKE (PHASE 2 UI REFACTOR)
# Tabs: Upload | Repository Summary | Validation
# All upload + analysis trigger logic and analysis-results logic preserved unchanged.
# ══════════════════════════════════════════════════════════════════════════════
if _step == 1:
    # ── One-shot scroll-to-top after the Home "Get Started" CTA ───────────────
    # Streamlit does not reset browser scroll position on st.rerun(). The Home
    # landing page is long, so after clicking the CTA near the bottom, the
    # much shorter Upload page would render starting off-screen above the
    # user's current scroll position — making the file uploader invisible
    # and requiring extra clicks/scrolling to find it. Fire a single scroll
    # reset exactly on the transition, then clear the flag so it never fights
    # the user's own scrolling on later reruns of this same page.
    if st.session_state.pop("_scroll_to_top_once", False):
        import streamlit.components.v1 as _components
        _components.html(
            "<script>window.parent.document.querySelector('section.main').scrollTo(0, 0);"
            "window.parent.scrollTo(0, 0);</script>",
            height=0,
        )

    wizard_progress(1)

    # ── back to landing (only meaningful once a landing page exists to
    #    return to — i.e. there's no analysis/upload in progress) ─────────────
    if "last_analysis_jobs" not in st.session_state and "wizard_uploaded_file_data" not in st.session_state:
        if st.button("← Back to Home", key="_step1_back_to_home"):
            st.session_state.pop("_home_show_upload", None)
            st.rerun()

    # ── compact header ────────────────────────────────────────────────────────
    page_header("📤", "Repository Intake", "Upload, review, and validate your Talend repository.")
    tab_upload, tab_repo_summary, tab_validation, tab_overview_dashboard = st.tabs(
        ["📤  Upload", "📊  Repository Summary", "✅  Validation", "🗂️  Dashboard"]
    )

    with tab_upload:
        if "prereq_result" not in st.session_state:
            st.session_state["prereq_result"] = check_prerequisites()
        _prereq = st.session_state["prereq_result"]

        if not _prereq["ok"]:
            st.error("Environment issue — " + " · ".join(_prereq["errors"]))
            st.stop()

        _ollama_available = _prereq["ollama_available"]

        # ── env pill + ollama toggle ──────────────────────────────────────────
        _ep_bg  = "#dcfce7" if _ollama_available else "#fff7ed"
        _ep_fg  = "#15803d" if _ollama_available else "#c2410c"
        _ep_txt = "✅ Ollama detected — AI analysis available" if _ollama_available else "⚠️ Ollama offline — rule engine active"
        _e1, _e2 = st.columns([4, 1])
        with _e1:
            st.markdown(
                f'<div style="background:{_ep_bg};border-radius:8px;padding:8px 12px;'
                f'font-size:12px;font-weight:600;color:{_ep_fg};">{_ep_txt}</div>',
                unsafe_allow_html=True,
            )
        with _e2:
            _use_ollama_toggle = st.checkbox(
                "Use Ollama AI",
                value=_ollama_available,
                disabled=not _ollama_available,
                help="Enable AI-powered analysis using local Ollama.",
                key="wizard_use_ollama_checkbox",
            )

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        # ── target + upload side by side ──────────────────────────────────────
        _tgt_col, _up_col = st.columns([1, 2], gap="large")
        with _tgt_col:
            st.markdown(
                '<div style="font-size:12px;font-weight:600;color:#64748b;'
                'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;">'
                'Migration Target</div>',
                unsafe_allow_html=True,
            )
            _target = st.selectbox(
                "target",
                ["Talend 8", "Talend Cloud", "Talend 7.4", "Talend 7.3"],
                key="wizard_target_version",
                label_visibility="collapsed",
            )
            st.markdown(
                '<div style="font-size:11px;color:#94a3b8;margin-top:2px;">'
                'Select your destination version</div>',
                unsafe_allow_html=True,
            )

        with _up_col:
            st.markdown(
                '<div style="font-size:12px;font-weight:600;color:#64748b;'
                'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;">'
                'Repository ZIP</div>',
                unsafe_allow_html=True,
            )
            # If a file was pre-loaded from the home page uploader, skip
            # the widget so the user is not asked to upload a second time.
            _prefilled = 'wizard_uploaded_file_data' in st.session_state
            if not _prefilled:
                _uploaded = st.file_uploader(
                    'zip',
                    type=['zip'],
                    label_visibility='collapsed',
                )
            else:
                _uploaded = None
            st.markdown(
                '<div style="font-size:11px;color:#94a3b8;margin-top:2px;">'
                'File → Export Items → ZIP Archive · 500 MB max</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        # ── upload progress + action ──────────────────────────────────────────────────
        if _uploaded:
            st.session_state['wizard_uploaded_file_name'] = _uploaded.name
            st.session_state['wizard_uploaded_file_data'] = _uploaded.getbuffer().tobytes()
            st.session_state['wizard_target_version_val'] = _target
            st.session_state['wizard_use_ollama'] = _use_ollama_toggle
            _prefilled = True

        if _prefilled and 'wizard_uploaded_file_data' in st.session_state:
            _fname = st.session_state.get('wizard_uploaded_file_name', 'repository.zip')
            _fsize_mb = round(len(st.session_state['wizard_uploaded_file_data']) / 1024 / 1024, 1)
            st.session_state['wizard_target_version_val'] = _target
            st.session_state['wizard_use_ollama'] = _use_ollama_toggle
            st.progress(1.0)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin:6px 0 12px;">'
                f'<span style="font-size:12px;font-weight:700;color:#15803d;">📦 {_fname}</span>'
                f'<span style="font-size:11px;color:#64748b;">{_fsize_mb} MB · ready to analyze</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button('▶  Analyze Repository', type='primary'):
                st.session_state['wizard_step'] = 2
                st.rerun()


    # ────────────────────────────────────────────────────────────────────────
    # TAB 2 — REPOSITORY SUMMARY (PHASE 2 UI REFACTOR)
    # ────────────────────────────────────────────────────────────────────────
    with tab_repo_summary:
        _intake_jobs = st.session_state.get("last_analysis_jobs", [])

        if not _intake_jobs:
            status_card(
                "No repository analyzed yet",
                "Upload a repository and run analysis from the Upload tab to see the summary.",
                "warning",
            )
        else:
            from app.tiap.inventory.inventory_parser import InventoryParser
            from app.tiap.profiling.component_profiler import ComponentProfiler

            _inventory = InventoryParser().build_inventory(_intake_jobs)
            _component_profile = ComponentProfiler().profile(_intake_jobs)
            _kpis = _inventory.get("kpis", {})
            _dist = _component_profile.get("component_distribution", {})

            _total_jobs = len(_intake_jobs)
            _total_components = sum(len(j["job_data"].get("components", [])) for j in _intake_jobs)

            render_kpi_row([
                {"label": "Jobs",       "value": str(_total_jobs),
                 "caption": "In scope", "color": "#5a7fbf"},
                {"label": "Joblets",    "value": str(_kpis.get("total_joblets", 0)),
                 "caption": "Reusable units", "color": "#3d8a6a"},
                {"label": "Routines",   "value": str(_kpis.get("total_routines", 0)),
                 "caption": "Shared code",    "color": "#7060b0"},
                {"label": "Components", "value": str(_total_components),
                 "caption": "Across all jobs", "color": "#b08040"},
            ])

            render_kpi_row([
                {"label": "Parent Jobs", "value": str(_kpis.get("total_parent_jobs", 0)), "color": "#5a7fbf"},
                {"label": "Child Jobs",  "value": str(_kpis.get("total_child_jobs", 0)),  "color": "#5a7fbf"},
                {"label": "Custom Components",     "value": str(_dist.get("CUSTOM", 0)),     "color": "#b08040"},
                {"label": "Deprecated Components", "value": str(_dist.get("DEPRECATED", 0)), "color": "#b06070"},
            ])

            panel_open("Component Distribution", "By component type across the repository", height=260)
            import pandas as pd
            _dist_rows = [{"Component Type": k, "Count": v} for k, v in _dist.items()]
            _dist_df = pd.DataFrame(_dist_rows)
            styled_dataframe(_dist_df, "component_distribution", use_container_width=True, hide_index=True)
            panel_close()

    # ────────────────────────────────────────────────────────────────────────
    # TAB 3 — VALIDATION (PHASE 2 UI REFACTOR)
    # ────────────────────────────────────────────────────────────────────────
    with tab_validation:
        _intake_jobs = st.session_state.get("last_analysis_jobs", [])

        if not _intake_jobs:
            status_card(
                "No repository analyzed yet",
                "Upload a repository and run analysis from the Upload tab to see validation results.",
                "warning",
            )
        else:
            from app.analyzers.readiness_scorer import RepositoryScoring
            from app.tiap.refactoring.technical_debt_detector import TechnicalDebtDetector
            from app.tiap.testing.regression_suite_builder import RegressionSuiteBuilder
            from app.tiap.governance.compliance_assessor import ComplianceAssessor

            _scoring    = RepositoryScoring().score(_intake_jobs)
            _debt       = TechnicalDebtDetector().analyze(_intake_jobs)
            _testing    = RegressionSuiteBuilder().build(_intake_jobs)
            _governance = ComplianceAssessor().assess(_intake_jobs)

            _render_status_badge_row([
                ("Migration Readiness", _score_to_rag(_scoring['migration_readiness_score'])),
                ("Cloud Readiness", _score_to_rag(_scoring['cloud_readiness_score'])),
                ("Documentation", _score_to_rag(_scoring['documentation_readiness_score'])),
                ("Testing Readiness", _score_to_rag(_scoring['testing_readiness_score'])),
            ])

            # _score_to_rag is the canonical rag_from_score (>=80 GREEN / >=60 AMBER / <60 RED)
            # imported from app.analyzers.health_score at the top of this module.
            with st.expander("🧮  Repository Complexity & Technical Debt", expanded=False):
                _render_status_badge_row([
                    ("Repository Complexity", _score_to_rag(_scoring["repository_complexity_score"])),
                    ("Technical Debt", "RED" if _debt["debt_score"] >= 60 else ("AMBER" if _debt["debt_score"] >= 30 else "GREEN")),
                ])
                _vc1, _vc2 = st.columns(2)
                with _vc1:
                    st.caption(f"Complexity score: {_scoring['repository_complexity_score']:.0f}/100")
                with _vc2:
                    st.caption(f"Debt score: {_debt['debt_score']:.0f}/100")

            with st.expander("🔒  PII & Compliance Findings", expanded=False):
                _pii = _governance.get("pii_detection", {})
                _pii_score = _pii.get("pii_risk_score", 0)
                _render_status_badge_row([
                    ("PII Risk", "RED" if _pii_score >= 60 else ("AMBER" if _pii_score >= 30 else "GREEN")),
                ])
                _pii_fields = _pii.get("fields", []) or _pii.get("findings", [])
                if _pii_fields:
                    panel_open("Detected PII Fields", height=240)
                    import pandas as pd
                    styled_dataframe(pd.DataFrame(_pii_fields), "pii_fields", use_container_width=True, hide_index=True)
                    panel_close()
                else:
                    st.caption("No PII fields detected.")

            with st.expander("🚨  High & Critical Risk Findings", expanded=False):
                _risks = [
                    (j["job_data"]["job_name"], r)
                    for j in _intake_jobs
                    for r in j.get("enterprise_risk_report", [])
                    if r.get("risk") in ("HIGH", "CRITICAL")
                ]
                if _risks:
                    _render_status_badge_row([("Risk Level", "RED")])
                    panel_open("Risk Findings", f"{len(_risks)} findings", height=260)
                    import pandas as pd
                    _risk_rows = [{
                        "Job": jn,
                        "Severity": r.get("risk", ""),
                        "Component": r.get("component", "Unknown component"),
                        "Message": r.get("message", "No details"),
                    } for jn, r in _risks]
                    styled_dataframe(pd.DataFrame(_risk_rows), "high_risk_findings", use_container_width=True, hide_index=True)
                    panel_close()
                else:
                    _render_status_badge_row([("Risk Level", "GREEN")])
                    st.caption("No high-risk findings — your repository looks clean!")

            with st.expander("🧪  Testing Readiness", expanded=False):
                _render_status_badge_row([
                    ("Testing Readiness", _score_to_rag(_testing["testing_readiness_score"])),
                ])
                st.caption(f"Testing readiness score: {_testing['testing_readiness_score']:.0f}/100")

    # ────────────────────────────────────────────────────────────────────────
    # TAB 4 — OVERVIEW DASHBOARD (PHASE 2B)
    # ────────────────────────────────────────────────────────────────────────
    with tab_overview_dashboard:
        if "last_analysis_jobs" not in st.session_state:
            st.markdown(
                '<div style="border:1.5px dashed #cbd5e1;border-radius:10px;'
                'padding:32px;text-align:center;color:#94a3b8;font-size:13px;margin-top:8px;">'
                '📊 Dashboard is available after analysis.<br>'
                '<span style="font-size:11px;">Upload a repository and click <strong>Analyze Repository</strong> to get started.</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            from app.ui.overview_dashboard_page import render_overview_dashboard
            render_overview_dashboard()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — ANALYZE (backend logic unchanged)
# ══════════════════════════════════════════════════════════════════════════════
elif _step == 2:
    wizard_progress(2)
    page_title(2, "Analyzing Repository",
               "This takes 1–3 minutes depending on repository size.")

    # Guard — need uploaded data
    if "wizard_uploaded_file_data" not in st.session_state:
        st.warning("No file found. Please go back to Step 1.")
        if st.button("← Back to Upload"):
            st.session_state["wizard_step"] = 1
            st.rerun()
        st.stop()

    def _abort_upload(title: str, detail: str) -> None:
        """Show a clear error and reset back to the Upload step."""
        st.error(f"**{title}**\n\n{detail}")
        st.session_state.pop("wizard_uploaded_file_data", None)
        st.session_state.pop("wizard_uploaded_file_name", None)
        st.session_state["wizard_step"] = 1
        if st.button("← Back to Upload", key="_abort_back_btn"):
            st.rerun()
        st.stop()

    # ── Already analyzed? Skip straight to step 3 ──
    if "last_analysis_jobs" in st.session_state and st.session_state.get("_analysis_complete"):
        st.session_state["wizard_step"] = 3
        st.rerun()

    # ── Run analysis ──────────────────────────────────────────────────────────
    status_placeholder = st.empty()
    progress_bar = st.progress(0)
    detail_placeholder = st.empty()
    steps = [
        "Parsing XML",
        "Building metadata",
        "Analysing components",
        "Scoring readiness",
        "Building lineage",
        "Generating Job360",
        "Complete",
    ]
    step_pct = {
        "Parsing XML": 5,
        "Building metadata": 15,
        "Analysing components": 70,
        "Scoring readiness": 82,
        "Building lineage": 90,
        "Generating Job360": 95,
        "Complete": 100,
    }

    def _update(msg: str, pct: int):
        status_placeholder.info(msg)
        progress_bar.progress(pct)

    # Write ZIP to disk
    _update(steps[0], step_pct[steps[0]])
    zip_path = f"uploaded_repository_{uuid.uuid4().hex}.zip"
    temp_repo = "temp_repository"
    output_dir = "output"

    if os.path.exists(temp_repo): shutil.rmtree(temp_repo, ignore_errors=True)
    if os.path.exists(output_dir): shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(temp_repo, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    with open(zip_path, "wb") as f:
        f.write(st.session_state["wizard_uploaded_file_data"])

    try:
        safe_extract(zip_path, temp_repo)
    except zipfile.BadZipFile:
        _abort_upload(
            "❌ Invalid ZIP file",
            "The uploaded file is not a valid ZIP archive. "
            "Please export your Talend repository via **File → Export Items → ZIP Archive** "
            "in Talend Open Studio and try again.",
        )
    finally:
        try: os.remove(zip_path)
        except: pass

    # ── Validate ZIP contains Talend .item files ──────────────────────────────
    _item_files = [
        p for root, _, files in os.walk(temp_repo)
        for f in files
        for p in [os.path.join(root, f)]
        if f.endswith(".item")
    ]
    _xml_files = [
        p for root, _, files in os.walk(temp_repo)
        for f in files
        for p in [os.path.join(root, f)]
        if f.endswith((".xml", ".item", ".properties"))
    ]

    if not _item_files:
        # Check what IS in the ZIP to give a meaningful message
        _all_exts = sorted({
            os.path.splitext(f)[1].lower()
            for _, _, files in os.walk(temp_repo)
            for f in files
            if os.path.splitext(f)[1]
        })
        _ext_hint = (
            f"Found file types: {', '.join(_all_exts[:8])}" if _all_exts
            else "The archive appears to be empty."
        )
        _abort_upload(
            "❌ Not a Talend repository",
            f"No Talend `.item` job files were found in the uploaded ZIP. {_ext_hint}\n\n"
            "Please upload a ZIP exported from **Talend Open Studio** via "
            "**File → Export Items → ZIP Archive**. "
            "The archive must contain `.item` files (e.g. `MyJob_0.1.item`).",
        )

    # ── Validate that .item files are well-formed XML ─────────────────────────
    def _try_parse(p):
        try:
            ET.parse(p)
            return True
        except Exception:
            return False

    _bad = [f for f in _item_files if not _try_parse(f)]

    if len(_bad) == len(_item_files):
        st.error("All .item files are corrupt or unsupported. Check your ZIP.")
        st.stop()
    elif _bad:
        st.warning(f"{len(_bad)} file(s) skipped — corrupt XML.")

    repo_path = temp_repo
    st.session_state["last_repo_path"] = repo_path

    target_version = st.session_state.get("wizard_target_version_val", "Talend 8")
    use_ollama = st.session_state.get("wizard_use_ollama", False)

    _update(steps[1], step_pct[steps[1]])
    source_version = detect_talend_version(repo_path)
    job_files = find_talend_jobs(repo_path)

    if not job_files:
        _abort_upload(
            "❌ No parseable jobs found",
            f"Found **{len(_item_files)} `.item` file(s)** but none could be parsed as Talend jobs. "
            "The files may be corrupted, password-protected, or from an unsupported Talend version.",
        )

    detail_placeholder.info(f"Found **{len(job_files)}** job files (source: {source_version})")

    # Process jobs
    all_jobs = []
    graph_builder = DependencyGraphBuilder()
    partial_transformer = PartialTransformer()
    patch_exporter = MigrationPatchExporter()
    summary_engine = TransformationSummary()
    advisor = ModernizationAdvisor()
    estimator = MigrationEstimator()
    risk_engine = RiskAnalyzer()
    all_transformations = []

    _update(steps[2], step_pct[steps[1]])
    for idx, file in enumerate(job_files):
        pct = step_pct[steps[1]] + int((step_pct[steps[2]] - step_pct[steps[1]]) * (idx + 1) / len(job_files))
        _update(steps[2], pct)
        detail_placeholder.info(f"Job {idx+1} of {len(job_files)}: {os.path.basename(file)}")
        try:
            job_data = _tma_cache.load_or_parse(file)
            if job_data["job_name"] == "INVALID_JOB":
                continue
            complexity = calculate_complexity(job_data)
            component_summary = analyze_components(job_data)
            legacy_risk_report = analyze_component_risks(job_data)
            cloud_readiness = calculate_cloud_readiness(job_data)
            dep_analyzer = DependencyAnalyzer(file)
            dependencies = dep_analyzer.analyze()
            graph_builder.build_graph(job_data["job_name"], dependencies)
            estimation = estimator.estimate(job_data, dependencies)
            enterprise_risk_report = risk_engine.analyze(job_data)
            transformations = partial_transformer.transform(job_data)
            modernization_report = advisor.analyze(job_data)
            all_transformations.extend(transformations)
            all_jobs.append({
                "job_data": job_data,
                "file_path": file,
                "complexity": complexity,
                "component_summary": component_summary,
                "legacy_risk_report": legacy_risk_report,
                "enterprise_risk_report": enterprise_risk_report,
                "cloud_readiness": cloud_readiness,
                "dependencies": dependencies,
                "estimation": estimation,
                "ai_recommendation": "",
                "transformations": transformations,
                "modernization_report": modernization_report,
            })
        except Exception as e:
            pass  # skip bad files silently

    # AI recommendations
    _update(steps[2], step_pct[steps[2]])
    for idx, job in enumerate(all_jobs):
        try:
            job["ai_recommendation"] = generate_migration_recommendation(
                job["job_data"], use_ollama=use_ollama,
                prompt_template=DEFAULT_MIGRATION_RECOMMENDATION_PROMPT,
            )
        except:
            job["ai_recommendation"] = "AI recommendation unavailable."
        progress_bar.progress(step_pct[steps[2]] + int(8 * (idx + 1) / max(len(all_jobs), 1)))

    # Enterprise analysis
    _update(steps[3], step_pct[steps[3]])
    custom_analysis = analyze_custom_components(all_jobs, use_ollama=use_ollama,
                                                prompt_template=DEFAULT_COMPONENT_RECOMMENDATION_PROMPT)
    deprecated_rows = build_deprecated_dashboard(all_jobs)
    readiness_score = calculate_readiness_score(all_jobs, custom_analysis, deprecated_rows)
    _effort_rates = st.session_state.get("assessment_config", ASSESSMENT_DEFAULT_CONFIG).get("effort", {})
    effort_estimate = estimate_repository_effort(all_jobs, custom_analysis, deprecated_rows, rates=_effort_rates)
    auto_fix_recs   = generate_auto_fix_recommendations(all_jobs)

    # Exports
    _update(steps[4], step_pct[steps[4]])
    token_checker = MigrationTokenChecker()
    studio_guide = StudioImportGuide()
    readiness_engine = MigrationReadiness()
    transformation_summary = summary_engine.summarize(all_transformations)
    patch_file = patch_exporter.export(output_dir, all_transformations)
    dependency_summary = [{"job_name": j["job_data"]["job_name"], "dependencies": j["dependencies"]} for j in all_jobs]
    export_dependency_summary(output_dir, dependency_summary)
    graph_data = graph_builder.export_graph_data()
    with open(os.path.join(output_dir, "dependency_graph_data.json"), "w") as f:
        json.dump(graph_data, f, indent=4)
    _update(steps[5], step_pct[steps[5]])
    report_file = export_excel(all_jobs)

    # Persist to session (unchanged keys)
    st.session_state.update({
        "last_analysis_jobs": all_jobs,
        "custom_analysis": custom_analysis,
        "deprecated_rows": deprecated_rows,
        "readiness_score": readiness_score,
        "effort_estimate": effort_estimate,
        "auto_fix_recs": auto_fix_recs,
        "wizard_report_file": report_file,
        "wizard_patch_file": patch_file,
        "wizard_source_version": source_version,
        "wizard_target_version_val": target_version,
        "_analysis_complete": True,
    })

    # Pre-warm the canonical Repository Health Score once so all consumers
    # (Executive Dashboard, Home, reports) share the same cached result
    # without recomputing it independently.
    try:
        from app.analyzers.health_score import get_health_score as _prewarm_hs
        _prewarm_hs(force_refresh=True)
    except Exception:
        pass

    # Log this run for the "Recent Projects" section on the landing page.
    # Best-effort only — never blocks the (already-complete) analysis flow.
    record_recent_project(
        name=st.session_state.get("wizard_uploaded_file_name", "").replace(".zip", ""),
        job_count=len(all_jobs),
        readiness=readiness_score.get("overall", "—"),
        source_version=source_version,
        target_version=target_version,
    )

    # Invalidate Phase 1C lineage cache so it rebuilds from the new repo's
    # .item files instead of stale data from a previous run or wrong source.
    import os as _os
    _lineage_cache_path = _os.path.join("cache", "phase_1c", "lineage_cache.json")
    try:
        if _os.path.exists(_lineage_cache_path):
            _os.remove(_lineage_cache_path)
    except OSError:
        pass
    try:
        from app.ui.cached_lineage_page import load_cached_lineage
        load_cached_lineage.clear()
    except Exception:
        pass
    try:
        from app.ui.overview_dashboard_page import _load_lineage_cache
        _load_lineage_cache.clear()
    except Exception:
        pass
    # Drop any session-state snapshot of the lineage cache
    st.session_state.pop("_overview_lineage_cache", None)
    st.session_state.pop("_cached_lineage_data", None)

    _update(steps[6], step_pct[steps[6]])
    time.sleep(0.5)
    st.session_state["wizard_step"] = 3
    st.rerun()

elif _step == 3:
    wizard_progress(3)

    if st.session_state.pop("_demo_repo_just_loaded", False):
        st.success("Demo loaded — 20 jobs, 4 complexity tiers, 3 industries")

    all_jobs        = st.session_state.get("last_analysis_jobs", [])
    readiness_score = st.session_state.get("readiness_score", {})
    effort_estimate = st.session_state.get("effort_estimate", {})
    auto_fix_recs   = st.session_state.get("auto_fix_recs", [])
    source_ver = st.session_state.get("wizard_source_version", "Unknown")
    target_ver = st.session_state.get("wizard_target_version_val", "Talend 8")

    if not all_jobs:
        st.warning("No analysis data. Please start from Step 1.")
        if st.button("← Start Over"):
            st.session_state["wizard_step"] = 1
            st.session_state.pop("_analysis_complete", None)
            st.rerun()
        st.stop()

    total_jobs       = len(all_jobs)
    total_components = sum(len(j["job_data"].get("components", [])) for j in all_jobs)
    total_high_risk  = sum(
        1 for j in all_jobs for r in j.get("enterprise_risk_report", [])
        if r.get("risk") in ("HIGH", "CRITICAL")
    )
    cloud_status = _cloud_status_summary(all_jobs)
    readiness   = readiness_score.get("overall", "RED")
    est_weeks   = effort_estimate.get("estimated_weeks", "N/A") if effort_estimate else "N/A"
    auto_pct    = effort_estimate.get("auto_pct", 0) if effort_estimate else 0
    try:
        est_weeks_display = f"~{max(1, round(float(est_weeks) * 7))}d" if float(est_weeks) < 1 else str(est_weeks)
    except (TypeError, ValueError):
        est_weeks_display = str(est_weeks)
    _risks = [
        (j["job_data"]["job_name"], r)
        for j in all_jobs
        for r in j.get("enterprise_risk_report", [])
        if r.get("risk") in ("HIGH", "CRITICAL")
    ]

    page_title(3, "Migration Review",
               f"Source: {source_ver}  →  Target: {target_ver}  ·  {total_jobs} jobs analyzed")

    # (the original used st.columns(5) with metric_card; render_kpi_row caps at 4,
    #  so Est. Weeks is included as the 4th tile; Cloud Status is folded into caption)
    _readiness_caption = {
        "GREEN": "Ready to migrate", "AMBER": "Needs review", "RED": "Remediation needed",
    }.get(readiness, readiness_score.get("status", ""))
    render_kpi_row([
        {"label": "Jobs",       "value": str(total_jobs),
         "caption": "In scope", "color": "#1d4ed8"},
        {"label": "Readiness",  "value": readiness,
         "caption": _readiness_caption,
         "color": "#15803d" if readiness == "GREEN" else "#b45309"},
        {"label": "High Risk",  "value": str(total_high_risk),
         "caption": "Findings to resolve" if total_high_risk else "None found",
         "color": "#be123c" if total_high_risk > 0 else "#15803d"},
        {"label": "Est. Weeks", "value": est_weeks_display,
         "caption": "Delivery baseline", "color": "#6d28d9"},
    ])

    # ── Concise readiness summary (badges + caption, no status_card blocks) ──
    _summary_lines = {
        "GREEN": "All checks passed. Repository is ready to migrate.",
        "AMBER": f"{total_high_risk} high-risk finding(s) to resolve before migrating.",
        "RED":   f"{total_high_risk} high-risk finding(s) require attention. Review before proceeding.",
    }
    _render_status_badge_row([
        ("Migration Readiness", readiness),
        ("High Risk", "RED" if total_high_risk > 0 else "GREEN"),
        ("Effort", "AMBER" if readiness != "GREEN" else "GREEN"),
    ])
    st.caption(_summary_lines.get(readiness, ""))

    if readiness != "GREEN" and _risks:
        _sev_color = {"CRITICAL": "#be123c", "HIGH": "#b45309"}
        _sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠"}
        for _jn, _r in _risks[:3]:
            _sev = _r.get("risk", "HIGH")
            _col = _sev_color.get(_sev, "#b45309")
            _emo = _sev_emoji.get(_sev, "🟠")
            st.markdown(
                f"""<div style="border-left:3px solid {_col};padding:6px 10px;margin-bottom:6px;
                background:rgba(0,0,0,0.03);border-radius:4px;font-size:0.82rem;line-height:1.4">
                <span style="font-weight:600;color:{_col}">{_emo} {_sev}</span>
                &nbsp;·&nbsp;<span style="opacity:.7">{_jn}</span>
                &nbsp;·&nbsp;<span style="font-style:italic">{_r.get("component","")}</span><br>
                {_r.get("message","No details")}</div>""",
                unsafe_allow_html=True,
            )
        if len(_risks) > 3:
            st.caption(f"… and {len(_risks)-3} more in the Risk Findings tab.")

    # ── Tabs: Summary | Risk | Jobs (unchanged) ──────────────────────────────
    tab_summary, tab_risk, tab_jobs = st.tabs(["📋  Summary", "🚨  Risk Findings", "📂  Jobs"])

    with tab_summary:
        _apply_summary_overflow_fix()
        with st.container(key="review_summary_overflow"):
            effort_reduction = min(45, max(10, int(auto_pct * 0.5))) if auto_pct else 10
            auto_fixable = sum(1 for r in auto_fix_recs if r.get("auto_fix"))
            st.markdown("##### Repository Metrics")
            render_kpi_row([
                {"label": "Components", "value": str(total_components), "caption": "Repository assets"},
                {"label": "Auto-Migratable", "value": f"{auto_pct}%", "caption": "Automation coverage"},
                {"label": "AI Reduction", "value": f"{effort_reduction}%",
                 "caption": "Of manual review time" if not auto_pct else "Estimated acceleration"},
                {"label": "Auto-Fixable", "value": str(auto_fixable), "caption": f"of {len(auto_fix_recs)} findings"},
            ])
            _render_status_badge_row([
                ("Jobs", str(total_jobs)),
                ("Components", str(total_components)),
                ("Auto-Migratable", f"{auto_pct}%"),
                ("Est. Weeks", str(est_weeks_display)),
            ])
        _close_summary_overflow_fix()

    with tab_risk:
        section_header("High & Critical Risk Findings")
        if _risks:
            _render_status_badge_row([("Risk Findings", "RED"), ("Count", str(len(_risks)))])
            import pandas as pd
            _risk_table = [{
                "Severity": r.get("risk", ""),
                "Job": jn,
                "Component": r.get("component", "Unknown component"),
                "Detail": r.get("message", "No details"),
            } for jn, r in _risks[:50]]
            styled_dataframe(pd.DataFrame(_risk_table), "tab_risk_findings", use_container_width=True, hide_index=True)
            if len(_risks) > 50:
                st.caption(f"… and {len(_risks)-50} more. See the Excel report for the full list.")
        else:
            _render_status_badge_row([("Risk Findings", "GREEN")])
            st.caption("No high-risk findings — your repository looks clean!")

    with tab_jobs:
        section_header("Job Summary")
        import pandas as pd
        _rows = []
        for j in all_jobs:
            jd = j["job_data"]
            cr = j["cloud_readiness"]
            hi_risk = sum(1 for r in j.get("enterprise_risk_report",[]) if r.get("risk") in ("HIGH","CRITICAL"))
            _rows.append({
                "Job": jd["job_name"],
                "Components": len(jd.get("components", [])),
                "Cloud Status": f"{_RAG_EMOJI.get(cr.get('rag',''), '')} {cr.get('rag','—')}",
                "High Risk": hi_risk,
                "Complexity": j["complexity"].get("level","—"),
            })
        _df = pd.DataFrame(_rows)
        styled_dataframe(_df, "job_summary", use_container_width=True, hide_index=True)
        for _idx, j in enumerate(all_jobs):
            jd = j["job_data"]
            if st.button(f"Job Analysis: {jd['job_name']}", key=f"job_analysis_btn_{jd['job_name']}_{_idx}"):
                st.session_state["selected_job_for_analysis"] = jd["job_name"]
                st.session_state["_advanced_page"] = "job_analysis"
                st.rerun()

    _c1, _c2, _c3, _c4 = st.columns([1, 1, 1, 1])
    with _c1:
        if st.button("← Back", use_container_width=True):
            st.session_state["wizard_step"] = 1
            st.session_state.pop("_analysis_complete", None)
            st.session_state.pop("last_analysis_jobs", None)
            st.rerun()
    with _c2:
        if st.button("Generate Reports →", type="primary", use_container_width=True):
            st.session_state["wizard_step"] = 4
            st.rerun()
    with _c3:
        if st.button("🔬 Deep Analysis", use_container_width=True,
                     help="Dependency graph, component analyzer, routine/joblet analyzer, AI hub"):
            st.session_state["_nav_idx2"] = 1
            st.rerun()
    with _c4:
        if st.button("📄 Generate Repository Report", use_container_width=True,
                     help="Generate a comprehensive repository-level migration report"):
            st.session_state["_show_repository_report"] = True
            st.rerun()

    st.markdown("---")
    with st.expander("📄 Generate Branded Executive PDF", expanded=False):
        from app.reports.executive_pdf_generator import generate_executive_pdf
        _pdf_client = st.text_input("Client name", key="exec_pdf_client_name", placeholder="e.g. Henry Schein")
        _pdf_logo   = st.file_uploader("Client logo (optional)", type=["png", "jpg"], key="exec_pdf_logo")
        if st.button("📄 Generate Branded PDF", key="exec_pdf_generate", use_container_width=True, type="primary"):
            with st.spinner("Generating…"):
                _logo_bytes = _pdf_logo.read() if _pdf_logo else None
                _pdf_bytes  = generate_executive_pdf(
                    session_state=st.session_state,
                    client_name=_pdf_client or "Client",
                    logo_path=_logo_bytes,
                )
            st.session_state["_exec_pdf_bytes"] = _pdf_bytes
        if st.session_state.get("_exec_pdf_bytes"):
            st.download_button(
                "⬇️ Download Executive PDF",
                data=st.session_state["_exec_pdf_bytes"],
                file_name=f"TMA_Executive_Assessment_{_pdf_client or 'Client'}.pdf",
                mime="application/pdf",
                key="exec_pdf_download",
                use_container_width=True,
            )

    if st.session_state.get("_show_repository_report"):
        st.markdown("---")
        section_header("Repository Report")
        _repo_report_jobs = all_jobs
        _rr_total = len(_repo_report_jobs)
        _rr_components = sum(len(j["job_data"].get("components", [])) for j in _repo_report_jobs)
        _rr_high_risk = sum(
            1 for j in _repo_report_jobs for r in j.get("enterprise_risk_report", [])
            if r.get("risk") in ("HIGH", "CRITICAL")
        )
        _rr_cloud_status = _cloud_status_summary(_repo_report_jobs)
        _rr_readiness = readiness_score.get("overall", "RED")
        _rr_hs = st.session_state.get("repository_health_score") or {}
        _rr_overall_status = _rr_hs.get("overall_status") or _rr_hs.get("risk_level") or "—"
        _rr_health_score = _rr_hs.get("overall_score") or _rr_hs.get("health_score") or "—"
        _rr_weeks = effort_estimate.get("estimated_weeks", "N/A") if effort_estimate else "N/A"
        _rr_hours = effort_estimate.get("estimated_hours", "N/A") if effort_estimate else "N/A"
        _rr_auto_pct = effort_estimate.get("auto_pct", 0) if effort_estimate else 0
        _rr_total_recommendations = len(st.session_state.get("auto_fix_recs", []))
        _complexity_counts = {}
        for _rj in _repo_report_jobs:
            _lvl = _rj.get("complexity", {}).get("level") or _rj.get("estimation", {}).get("complexity", "UNKNOWN")
            _complexity_counts[_lvl] = _complexity_counts.get(_lvl, 0) + 1

        render_kpi_row([
            {"label": "Total Jobs", "value": str(_rr_total), "caption": "In scope", "color": "#1d4ed8"},
            {"label": "Total Hours", "value": str(_rr_hours), "caption": "Estimated effort", "color": "#6d28d9"},
            {"label": "Total Recommendations", "value": str(_rr_total_recommendations), "caption": "Auto-fix findings", "color": "#b45309"},
        ])

        _render_repository_executive_summary(
            st.session_state.get('wizard_source_version', 'Unknown'),
            st.session_state.get('wizard_target_version_val', 'Talend 8'),
            [
                ("Total Jobs", _rr_total),
                ("Total Components", _rr_components),
                ("Migration Readiness", _rr_readiness),
                ("Overall Status", _rr_overall_status),
                ("Repository Health Score", f"{_rr_health_score}/100"),
                ("High/Critical Risk Findings", _rr_high_risk),
                ("Estimated Delivery", f"{_rr_weeks} weeks"),
                ("Auto-Migratable", f"{_rr_auto_pct}%"),
            ],
        )

        st.markdown("#### Complexity Distribution")
        for _lvl, _cnt in _complexity_counts.items():
            st.markdown(f"- **{_lvl}**: {_cnt} job(s)")

        st.markdown("#### Job Summary")
        _rr_rows = []
        for _rj in _repo_report_jobs:
            _jd = _rj["job_data"]
            _cr = _rj["cloud_readiness"]
            _hi = sum(1 for r in _rj.get("enterprise_risk_report", []) if r.get("risk") in ("HIGH", "CRITICAL"))
            _rr_rows.append({
                "Job": _jd["job_name"],
                "Components": len(_jd.get("components", [])),
                "Complexity": _rj.get("complexity", {}).get("level", "—"),
                "Cloud Status": f"{_RAG_EMOJI.get(_cr.get('rag',''), '')} {_cr.get('rag','—')}",
                "High Risk": _hi,
            })
        styled_dataframe(pd.DataFrame(_rr_rows), "repo_report_jobs", use_container_width=True, hide_index=True)

        st.markdown("#### High & Critical Risk Findings")
        _rr_risks = [
            {"Job": jn, "Severity": r.get("risk", ""), "Component": r.get("component", "Unknown"), "Message": r.get("message", "")}
            for j in _repo_report_jobs
            for jn, r in [(j["job_data"]["job_name"], r) for r in j.get("enterprise_risk_report", [])
                          if r.get("risk") in ("HIGH", "CRITICAL")]
        ]
        if _rr_risks:
            styled_dataframe(pd.DataFrame(_rr_risks), "repo_report_risks", use_container_width=True, hide_index=True)
        else:
            st.success("No high-risk findings detected.")

        _rr_report_text = f"""REPOSITORY MIGRATION REPORT
===========================
Source: {st.session_state.get('wizard_source_version', 'Unknown')} -> Target: {st.session_state.get('wizard_target_version_val', 'Talend 8')}

EXECUTIVE SUMMARY
-----------------
Total Jobs: {_rr_total}
Total Components: {_rr_components}
Migration Readiness: {_rr_readiness}
Overall Status: {_rr_overall_status}
Repository Health Score: {_rr_health_score}/100
High/Critical Risk Findings: {_rr_high_risk}
Estimated Delivery: {_rr_weeks} weeks
Auto-Migratable: {_rr_auto_pct}%

COMPLEXITY DISTRIBUTION
-----------------------
""" + "\n".join(f"{k}: {v} job(s)" for k, v in _complexity_counts.items()) + """

JOB SUMMARY
-----------
""" + "\n".join(
    f"{r['Job']} | {r['Components']} components | {r['Complexity']} | {r['Cloud Status']} cloud | {r['High Risk']} high-risk"
    for r in _rr_rows
) + """

HIGH & CRITICAL RISK FINDINGS
------------------------------
""" + ("\n".join(f"[{r['Severity']}] {r['Job']} / {r['Component']}: {r['Message']}" for r in _rr_risks) if _rr_risks else "None")

        st.download_button(
            "⬇️ Download Repository Report (.txt)",
            data=_rr_report_text,
            file_name="repository_migration_report.txt",
            mime="text/plain",
            key="dl_repo_report_txt",
        )

        # ── Repository Report ZIP: Executive Summary + Job Analysis Reports + Recommendations ──
        _rr_zip_bytes = _build_repository_report_zip(_repo_report_jobs, readiness_score, effort_estimate)

        st.download_button(
            "⬇️ Download Repository Report (.zip)",
            data=_rr_zip_bytes,
            file_name="repository_report.zip",
            mime="application/zip",
            key="dl_repo_report_zip",
        )
        if st.button("✕ Close Report", key="close_repo_report"):
            st.session_state["_show_repository_report"] = False
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — GENERATE (backend logic unchanged)
# ══════════════════════════════════════════════════════════════════════════════
elif _step == 4:
    wizard_progress(4)
    page_title(4, "Generate Reports",
               "Choose what to include in your migration report package.")

    all_jobs = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        empty_state_card("No data", "Start from Step 1.")
        if st.button("← Start Over"):
            st.session_state["wizard_step"] = 1
            st.rerun()
        st.stop()

    section_header("Report Options", "Select the outputs you need.")

    col_l, col_r = st.columns(2)
    with col_l:
        inc_excel = st.checkbox("📊  Excel Migration Report", value=True,
                                help="Full job inventory, risk breakdown, component analysis.")
        inc_patch = st.checkbox("🔧  Migration Patch (JSON)", value=True,
                                help="Automated XML transformation patch file.")
    with col_r:
        inc_deps  = st.checkbox("🔗  Dependency Graph", value=True,
                                help="Job-to-job dependency map.")
        inc_exec  = st.checkbox("📋  Executive Summary", value=False,
                                help="Boardroom-ready summary (requires extended generation).")

    if False:
        st.text_area("Custom report header / context", height=80, key="rpt_custom_context",
                     placeholder="e.g. 'This repository belongs to the Finance ETL team…'")

    _c1, _c2, _ = st.columns([1, 1, 3])
    with _c1:
        if st.button("← Back to Review", use_container_width=True):
            st.session_state["wizard_step"] = 3
            st.rerun()
    with _c2:
        if st.button("⚙  Generate Now", type="primary", use_container_width=True):
            _gen_status = st.empty()
            _gen_bar = st.progress(0)

            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)

            steps_done = 0
            steps_total = sum([inc_excel, inc_patch, inc_deps, inc_exec])

            if inc_excel:
                _gen_status.info("Generating Excel report…")
                try:
                    rpt = export_excel(all_jobs)
                    st.session_state["wizard_report_file"] = rpt
                except: pass
                steps_done += 1; _gen_bar.progress(steps_done / max(steps_total,1))

            if inc_patch:
                _gen_status.info("Generating migration patch…")
                try:
                    pt = PartialTransformer()
                    pe = MigrationPatchExporter()
                    se = TransformationSummary()
                    txs = []
                    for j in all_jobs:
                        txs.extend(pt.transform(j["job_data"]))
                    patch_f = pe.export(output_dir, txs)
                    st.session_state["wizard_patch_file"] = patch_f
                except: pass
                steps_done += 1; _gen_bar.progress(steps_done / max(steps_total,1))

            if inc_deps:
                _gen_status.info("Exporting dependency graph…")
                try:
                    dep_sum = [{"job_name": j["job_data"]["job_name"], "dependencies": j["dependencies"]} for j in all_jobs]
                    export_dependency_summary(output_dir, dep_sum)
                except: pass
                steps_done += 1; _gen_bar.progress(steps_done / max(steps_total,1))

            if inc_exec:
                _gen_status.info("Generating executive summary…")
                # placeholder — real generation via tiap pipeline
                time.sleep(1)
                steps_done += 1; _gen_bar.progress(1.0)

            _gen_status.empty()
            _gen_bar.empty()
            st.session_state["wizard_step"] = 5
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — DOWNLOAD (backend logic unchanged)
# ══════════════════════════════════════════════════════════════════════════════
elif _step == 5:
    wizard_progress(5)

    all_jobs   = st.session_state.get("last_analysis_jobs", [])
    readiness  = st.session_state.get("readiness_score", {}).get("overall", "RED")
    total_jobs = len(all_jobs)
    total_hr   = sum(1 for j in all_jobs for r in j.get("enterprise_risk_report",[]) if r.get("risk") in ("HIGH","CRITICAL"))
    est_weeks  = st.session_state.get("effort_estimate", {}).get("estimated_weeks","N/A")
    source_ver = st.session_state.get("wizard_source_version","Unknown")
    target_ver = st.session_state.get("wizard_target_version_val","Talend 8")

    success_banner(
        "Your migration report is ready",
        f"{total_jobs} jobs analyzed  ·  Readiness: {readiness}  ·  {total_hr} high-risk findings  ·  Estimated {est_weeks} weeks  ·  {source_ver} → {target_ver}"
    )

    render_kpi_row([
        {"label": "Jobs Analyzed",  "value": str(total_jobs),  "color": "#1d4ed8"},
        {"label": "Readiness",      "value": readiness,  "color": "#15803d"},
        {"label": "High Risk",      "value": str(total_hr),    "color": "#be123c"},
        {"label": "Est. Weeks",     "value": str(est_weeks),   "color": "#6d28d9"},
    ])

    section_header("Download Reports")

    _report_file = st.session_state.get("wizard_report_file")
    _patch_file  = st.session_state.get("wizard_patch_file")
    _dep_file    = os.path.join("output", "dependency_summary.json")

    dl_c1, dl_c2, dl_c3, dl_c4 = st.columns(4)

    with dl_c1:
        download_card("📊", "Excel Report", "Full job inventory, risks, components, estimates")
        if _report_file and os.path.exists(_report_file):
            with open(_report_file, "rb") as f:
                st.download_button("Download Excel", f, "migration_report.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key="dl_excel")
        else:
            st.button("Download Excel", disabled=True, use_container_width=True, key="dl_excel_dis")

    with dl_c2:
        download_card("🔧", "Migration Patch", "Automated XML transformation patch")
        if _patch_file and os.path.exists(_patch_file):
            with open(_patch_file, "rb") as f:
                st.download_button("Download Patch", f, "migration_patch.json",
                    "application/json", use_container_width=True, key="dl_patch")
        else:
            st.button("Download Patch", disabled=True, use_container_width=True, key="dl_patch_dis")

    with dl_c3:
        download_card("🔗", "Dependency Graph", "Job-to-job dependency relationships")
        if os.path.exists(_dep_file):
            with open(_dep_file, "rb") as f:
                st.download_button("Download Dependencies", f, "dependency_summary.json",
                    "application/json", use_container_width=True, key="dl_deps")
        else:
            st.button("Download Dependencies", disabled=True, use_container_width=True, key="dl_deps_dis")

    with dl_c4:
        download_card("📦", "Repository Report (ZIP)", "Executive summary, job analysis reports, recommendations")
        _rr_zip_bytes_s5 = _build_repository_report_zip(
            all_jobs, st.session_state.get("readiness_score", {}), st.session_state.get("effort_estimate", {})
        )
        st.download_button("Download Repository Report", _rr_zip_bytes_s5, "repository_report.zip",
            "application/zip", use_container_width=True, key="dl_repo_report_zip_s5")

    section_header("What's Next?")
    next_c1, next_c2, next_c3 = st.columns(3)
    with next_c1:
        status_card("Review risk findings",
                    "Open the Excel report and work through the High/Critical tab with your development team.",
                    "warning")
    with next_c2:
        status_card("Run migration in Talend Studio",
                    "Apply the migration patch and import your jobs into Talend 8 or Talend Cloud.",
                    "info")
    with next_c3:
        status_card("Validate & test",
                    "Run regression tests against migrated jobs before go-live.",
                    "success")

    _ca, _cb, _ = st.columns([1, 1, 3])
    with _ca:
        if st.button("← Back to Review", use_container_width=True):
            st.session_state["wizard_step"] = 3
            st.rerun()
    with _cb:
        render_analyze_new_repo_button(key="wizard_step4_analyze_new", use_container_width=True)
