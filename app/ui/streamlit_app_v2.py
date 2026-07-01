"""
Artha TMA — Redesigned Wizard UI (v2)
5-step flow: Upload → Analyze → Review → Generate → Download
Business-user first. Minimal cognitive load. Enterprise SaaS look.
"""
import json
import os
import shutil
import time
import uuid
import zipfile

import streamlit as st

from app.analyzers.health_score import rag_from_score as _score_to_rag
from app.utils.zip_extractor import safe_extract

# ── Design System v2 ──────────────────────────────────────────────────────────

def _cloud_rag(cr: dict) -> str:
    """Get RAG status from a cloud_readiness dict (supports both old score and new rag fields)."""
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    return _score_to_rag(cr.get("score", 0))

from app.ui.design_system_v2 import (
    apply_wizard_theme,
    download_card,
    empty_state_card,
    metric_card,
    page_title,
    render_kpi_badge,
    section_header,
    sidebar_brand,
    sidebar_status,
    status_card,
    success_banner,
    topbar,
    wizard_progress,
)

# ── Core analysis imports ─────────────────────────────────────────────────────
from app.parser.repository_scanner import find_talend_jobs
from app.parser.talend_xml_parser import TalendJobParser
from app.cache.cache_manager import CacheManager as _CacheManager

# Module-level cache instance (shared across Streamlit reruns)
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

# ── Streamlit page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Artha Talend — Migration Accelerator",
    layout="wide",
    page_icon="🚀",
    initial_sidebar_state="expanded",
)
apply_wizard_theme()

# ── Sidebar ────────────────────────────────────────────────────────────────────
sidebar_brand()

_PAGES = ["🏠  Home", "🔄  Version Converter", "📊  Executive Dashboard", "⚙️  Settings"]
st.sidebar.markdown('<span class="tma-nav-label">Menu</span>', unsafe_allow_html=True)
_sel = st.sidebar.radio("nav", _PAGES, label_visibility="collapsed",
                        index=st.session_state.get("_nav_idx2", 0))
st.session_state["_nav_idx2"] = _PAGES.index(_sel)

_has_analysis = "last_analysis_jobs" in st.session_state
_job_count = len(st.session_state.get("last_analysis_jobs", []))
sidebar_status(_has_analysis, _job_count)

# Advanced tools collapsed away from main flow
with st.sidebar.expander("🔧 Advanced", expanded=False):
    st.caption("AI / Ollama, prompts, templates")
    if st.button("Ollama Settings", use_container_width=True, key="nav_ollama"):
        st.session_state["_advanced_page"] = "ollama"
    if st.button("Prompt Library", use_container_width=True, key="nav_prompts"):
        st.session_state["_advanced_page"] = "prompts"
    if st.button("Template Manager", use_container_width=True, key="nav_templates"):
        st.session_state["_advanced_page"] = "templates"

# ── Routing for non-wizard pages ───────────────────────────────────────────────
if _sel == "🔄  Version Converter":
    from app.ui.version_converter_page import render_converter
    topbar("Version Converter")
    render_converter()
    st.stop()

if _sel == "📊  Executive Dashboard":
    from app.ui.dashboard import render_executive_dashboard
    topbar("Executive Dashboard")
    render_executive_dashboard()
    st.stop()

if _sel == "⚙️  Settings":
    topbar("Settings")
    section_header("Settings", "Configure migration defaults and display preferences.")
    with st.expander("Executive Assumptions", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input("Blended daily rate ($)", 100, 5000, 900, 50, key="default_blended_rate")
        with c2:
            st.slider("AI effort reduction (%)", 5, 60, 30, key="default_ai_reduction")
        with c3:
            st.selectbox("Target platform", ["Talend 8", "Talend Cloud", "Hybrid"], key="default_target_platform")
    with st.expander("Display", expanded=False):
        st.toggle("Start in boardroom mode", True, key="settings_boardroom_default")
        st.toggle("Hide raw evidence by default", True, key="settings_hide_raw_default")
    st.stop()

# ── WIZARD HOME ────────────────────────────────────────────────────────────────
topbar("Migration Wizard")

# Determine current wizard step from session state
_step = st.session_state.get("wizard_step", 1)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
if _step == 1:
    wizard_progress(1)

    # prereq check
    if "prereq_result" not in st.session_state:
        st.session_state["prereq_result"] = check_prerequisites()
    _prereq = st.session_state["prereq_result"]

    if not _prereq["ok"]:
        st.error("Environment setup required — " + " · ".join(_prereq["errors"]))
        st.stop()

    # ── compact header row ────────────────────────────────────────────────────
    _ai_ok = _prereq["ollama_available"]
    _ai_pill = (
        '<span style="background:#dcfce7;color:#15803d;font-size:11px;font-weight:700;'
        'padding:2px 10px;border-radius:20px;">✅ Ollama AI</span>'
        if _ai_ok else
        '<span style="background:#fff7ed;color:#c2410c;font-size:11px;font-weight:700;'
        'padding:2px 10px;border-radius:20px;">⚠️ AI offline</span>'
    )
    st.markdown(
        f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:14px;">'
        f'<span style="font-size:20px;font-weight:800;color:#0f172a;">Repository Intake</span>'
        f'{_ai_pill}</div>',
        unsafe_allow_html=True,
    )

    # ── two-column form ───────────────────────────────────────────────────────
    _fc1, _fc2 = st.columns([1, 2], gap="large")

    with _fc1:
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

    with _fc2:
        st.markdown(
            '<div style="font-size:12px;font-weight:600;color:#64748b;'
            'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;">'
            'Repository ZIP</div>',
            unsafe_allow_html=True,
        )
        _uploaded = st.file_uploader(
            "zip",
            type=["zip"],
            label_visibility="collapsed",
        )
        st.markdown(
            '<div style="font-size:11px;color:#94a3b8;margin-top:2px;">'
            'File → Export Items → ZIP Archive · 500 MB max</div>',
            unsafe_allow_html=True,
        )

    # ── action ────────────────────────────────────────────────────────────────
    if _uploaded:
        st.session_state["wizard_uploaded_file_name"] = _uploaded.name
        st.session_state["wizard_uploaded_file_data"] = _uploaded.getbuffer().tobytes()
        st.session_state["wizard_target_version_val"] = _target
        st.session_state["wizard_use_ollama"] = _ai_ok

        st.markdown(
            f'<div style="font-size:12px;color:#15803d;font-weight:600;margin:6px 0 8px;">'
            f'📦 {_uploaded.name} — ready</div>',
            unsafe_allow_html=True,
        )
        if st.button("▶  Analyze Repository", type="primary"):
            st.session_state["wizard_step"] = 2
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — ANALYZE
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

    # ── Already analyzed? Skip straight to step 3 ──
    if "last_analysis_jobs" in st.session_state and st.session_state.get("_analysis_complete"):
        st.session_state["wizard_step"] = 3
        st.rerun()

    # ── Run analysis ──────────────────────────────────────────────────────────
    status_placeholder = st.empty()
    progress_bar = st.progress(0)
    detail_placeholder = st.empty()

    def _update(msg: str, pct: int):
        status_placeholder.markdown(f"""
        <div style="background:#eff6ff;border:1px solid #dbeafe;border-radius:10px;
                    padding:16px 20px;margin:8px 0;">
            <div style="font-size:13px;font-weight:600;color:#1d4ed8;">{msg}</div>
        </div>
        """, unsafe_allow_html=True)
        progress_bar.progress(pct)

    # Write ZIP to disk
    _update("Extracting repository…", 5)
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
        st.error("Invalid ZIP file. Please re-export from Talend Open Studio.")
        os.remove(zip_path)
        st.stop()
    finally:
        try: os.remove(zip_path)
        except: pass

    repo_path = temp_repo
    st.session_state["last_repo_path"] = repo_path

    target_version = st.session_state.get("wizard_target_version_val", "Talend 8")
    use_ollama = st.session_state.get("wizard_use_ollama", False)

    _update("Discovering Talend jobs…", 10)
    source_version = detect_talend_version(repo_path)
    job_files = find_talend_jobs(repo_path)

    if not job_files:
        st.error("No Talend jobs found in this repository. Check the ZIP contents.")
        st.stop()

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

    for idx, file in enumerate(job_files):
        pct = 10 + int(50 * (idx + 1) / len(job_files))
        _update(f"Analyzing job {idx+1} of {len(job_files)}: {os.path.basename(file)}", pct)
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
    _update("Running AI analysis…", 65)
    for idx, job in enumerate(all_jobs):
        try:
            job["ai_recommendation"] = generate_migration_recommendation(
                job["job_data"], use_ollama=use_ollama,
                prompt_template=DEFAULT_MIGRATION_RECOMMENDATION_PROMPT,
            )
        except:
            job["ai_recommendation"] = "AI recommendation unavailable."
        progress_bar.progress(65 + int(15 * (idx + 1) / max(len(all_jobs), 1)))

    # Enterprise analysis
    _update("Computing migration readiness scores…", 82)
    custom_analysis = analyze_custom_components(all_jobs, use_ollama=use_ollama,
                                                prompt_template=DEFAULT_COMPONENT_RECOMMENDATION_PROMPT)
    deprecated_rows = build_deprecated_dashboard(all_jobs)
    readiness_score = calculate_readiness_score(all_jobs, custom_analysis, deprecated_rows)
    effort_estimate = estimate_repository_effort(all_jobs, custom_analysis, deprecated_rows)
    auto_fix_recs   = generate_auto_fix_recommendations(all_jobs)

    # Exports
    _update("Generating reports…", 92)
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
    report_file = export_excel(all_jobs)

    # Persist to session
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

    _update("✅ Analysis complete", 100)
    time.sleep(0.5)
    st.session_state["wizard_step"] = 3
    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — REVIEW
# ══════════════════════════════════════════════════════════════════════════════
elif _step == 3:
    wizard_progress(3)

    all_jobs = st.session_state.get("last_analysis_jobs", [])
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

    total_jobs = len(all_jobs)
    total_components = sum(len(j["job_data"].get("components", [])) for j in all_jobs)
    total_high_risk = sum(
        1 for j in all_jobs for r in j.get("enterprise_risk_report", [])
        if r.get("risk") in ("HIGH", "CRITICAL")
    )
    _rag_counts = {"GREEN": 0, "AMBER": 0, "RED": 0}
    for j in all_jobs:
        _rag_counts[_cloud_rag(j["cloud_readiness"])] = _rag_counts.get(_cloud_rag(j["cloud_readiness"]), 0) + 1
    _dominant_rag = max(_rag_counts, key=_rag_counts.get) if total_jobs else "AMBER"
    avg_cloud = _dominant_rag  # RAG status replacing numeric score
    readiness = readiness_score.get("overall", "RED")
    est_weeks  = effort_estimate.get("estimated_weeks", "N/A") if effort_estimate else "N/A"
    auto_pct   = effort_estimate.get("auto_pct", 0) if effort_estimate else 0

    page_title(3, "Migration Review",
               f"Source: {source_ver}  →  Target: {target_ver}  ·  {total_jobs} jobs analyzed")

    # ── KPI row (interactive — click each card for explanation + editable settings) ──
    c1, c2, c3, c4, c5 = st.columns(5)

    # Build detail payloads so popovers show rich explanations
    _jobs_details = {
        "total_jobs":     total_jobs,
        "in_scope":       total_jobs,
        "auto_migratable": f"{auto_pct}%",
        "manual_review":  total_jobs - int(total_jobs * auto_pct / 100) if auto_pct else total_jobs,
    }
    _readiness_details = {
        "green_ceiling": st.session_state.get("readiness_green_ceiling", 5),
        "amber_ceiling": st.session_state.get("readiness_amber_ceiling", 25),
        "notes": (
            f"Current score: {readiness_score.get('score', 'N/A')}. "
            f"Status: {readiness_score.get('status', 'N/A')}. "
            "Open 'Tune Readiness Thresholds' below to customise the GREEN/AMBER/RED boundaries."
        ),
    }
    _rag_color = {"GREEN": "green", "AMBER": "amber", "RED": "red"}.get(avg_cloud, "teal")
    _cr_positive = [c for j in all_jobs for c in j["cloud_readiness"].get("positive_factors", [])][:5] or ["Standard Components"]
    _cr_negative = [c for j in all_jobs for c in j["cloud_readiness"].get("negative_factors", [])][:5] or ["Custom Java", "Unsupported Components"]
    _cr_details = {
        "positive": list(dict.fromkeys(_cr_positive)),
        "negative": list(dict.fromkeys(_cr_negative)),
        "readiness_score": avg_cloud,
    }
    _risk_details = {
        "flag_tjava":      st.session_state.get("risk_rule_flag_tjava",      True),
        "flag_deprecated": st.session_state.get("risk_rule_flag_deprecated", True),
        "flag_creds":      st.session_state.get("risk_rule_flag_creds",      True),
        "flag_context":    st.session_state.get("risk_rule_flag_context",    True),
        "notes": (
            f"{total_high_risk} HIGH/CRITICAL finding(s) detected across {total_jobs} job(s). "
            "Open 'Adjust Risk Rules' below to change which component types are flagged."
        ),
    }
    _effort_raw = effort_estimate or {}
    _effort_details = {
        "breakdown": {
            "Discovery & scoping": round(_effort_raw.get("estimated_weeks", 0) * 0.10, 1),
            "Component migration": round(_effort_raw.get("estimated_weeks", 0) * 0.40, 1),
            "Java code porting":   round(_effort_raw.get("estimated_weeks", 0) * 0.20, 1),
            "Testing & QA":        round(_effort_raw.get("estimated_weeks", 0) * 0.20, 1),
            "UAT & sign-off":      round(_effort_raw.get("estimated_weeks", 0) * 0.10, 1),
        },
        "blended_rate": st.session_state.get("default_blended_rate", 900),
        "ai_reduction": st.session_state.get("default_ai_reduction",  30),
        "team_size":    st.session_state.get("default_team_size",     "2 engineers"),
        "notes": (
            f"Baseline: {est_weeks} week(s). "
            f"Auto-migratable: {auto_pct}%. "
            "Open 'Tune Effort Assumptions' below to adjust team size, daily rate, and AI reduction."
        ),
    }

    _readiness_status = readiness
    with c1:
        render_kpi_badge("Jobs",          total_jobs,         "In scope",          "blue",
                         details=_jobs_details,    key="review_kpi_jobs")
    with c2:
        render_kpi_badge("Readiness",     _readiness_status,  readiness_score.get("status", ""),
                         "green" if readiness == "GREEN" else "amber",
                         details=_readiness_details, key="review_kpi_readiness")
    with c3:
        render_kpi_badge("Cloud Readiness", avg_cloud,        "Talend 8 / Cloud fit", _rag_color,
                         details=_cr_details,      key="review_kpi_cloud")
    with c4:
        render_kpi_badge("High Risk",     total_high_risk,    "Findings to resolve",
                         "red" if total_high_risk > 0 else "green",
                         details=_risk_details,    key="review_kpi_risk")
    with c5:
        render_kpi_badge("Est. Weeks",    est_weeks,          "Delivery baseline",  "purple",
                         details=_effort_details,  key="review_kpi_effort")

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Readiness card ────────────────────────────────────────────────────────
    if readiness == "GREEN":
        status_card("✅ Ready to migrate",
                    "Your repository is ready to migrate. Proceed to generate reports.",
                    "success")
    elif readiness == "AMBER":
        status_card("⚠️ Moderate effort required",
                    "Review and resolve the high-risk findings before migrating.",
                    "warning")
    else:
        status_card("❌ Significant remediation needed",
                    "Substantial work required before migration can proceed.",
                    "error")

    # ── Tabs: Summary | Risk | Jobs ──────────────────────────────────────────
    tab_summary, tab_risk, tab_jobs = st.tabs(["📋  Summary", "🚨  Risk Findings", "📂  Jobs"])

    with tab_summary:
        section_header("Migration Overview")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"""
            | Metric | Value |
            |--------|-------|
            | Total jobs | {total_jobs} |
            | Total components | {total_components} |
            | Auto-migratable | {auto_pct}% |
            | Estimated weeks | {est_weeks} |
            """)
        with col_b:
            effort_reduction = min(45, max(10, int(auto_pct * 0.5))) if auto_pct else 10
            status_card("AI Opportunity",
                        f"AI-assisted analysis can reduce migration effort by approximately {effort_reduction}%.",
                        "info")
            auto_fixable = sum(1 for r in auto_fix_recs if r.get("auto_fix"))
            if auto_fixable:
                status_card("Auto-fix candidates",
                            f"{auto_fixable} of {len(auto_fix_recs)} issues appear auto-fixable.",
                            "success")

    with tab_risk:
        section_header("High & Critical Risk Findings")
        _risks = [
            (j["job_data"]["job_name"], r)
            for j in all_jobs
            for r in j.get("enterprise_risk_report", [])
            if r.get("risk") in ("HIGH", "CRITICAL")
        ]
        if _risks:
            for job_name, risk in _risks[:20]:  # cap at 20 for readability
                _color = "error" if risk.get("risk") == "CRITICAL" else "warning"
                status_card(
                    f"{risk.get('risk','')} · {job_name}",
                    f"{risk.get('component','Unknown component')} — {risk.get('message','No details')}",
                    _color,
                )
            if len(_risks) > 20:
                st.caption(f"… and {len(_risks)-20} more. See the Excel report for the full list.")
        else:
            status_card("No high-risk findings", "Your repository looks clean!", "success")

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
                "Cloud Readiness": _cloud_rag(cr),
                "High Risk": hi_risk,
                "Complexity": j["complexity"].get("level","—"),
            })
        _df = pd.DataFrame(_rows)
        st.dataframe(_df, use_container_width=True, hide_index=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    _c1, _c2, _ = st.columns([1, 1, 3])
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

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — GENERATE
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
        st.info("These settings affect AI-generated narrative sections only.")
        st.text_area("Custom report header / context", height=80, key="rpt_custom_context",
                     placeholder="e.g. 'This repository belongs to the Finance ETL team…'")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

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
# STEP 5 — DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════
elif _step == 5:
    wizard_progress(5)

    all_jobs     = st.session_state.get("last_analysis_jobs", [])
    readiness    = st.session_state.get("readiness_score", {}).get("overall", "RED")
    total_jobs   = len(all_jobs)
    total_hr     = sum(1 for j in all_jobs for r in j.get("enterprise_risk_report",[]) if r.get("risk") in ("HIGH","CRITICAL"))
    est_weeks    = st.session_state.get("effort_estimate", {}).get("estimated_weeks","N/A")
    source_ver   = st.session_state.get("wizard_source_version","Unknown")
    target_ver   = st.session_state.get("wizard_target_version_val","Talend 8")

    success_banner(
        "Your migration report is ready",
        f"{total_jobs} jobs analyzed  ·  Readiness: {readiness}  ·  {total_hr} high-risk findings  ·  Estimated {est_weeks} weeks  ·  {source_ver} → {target_ver}"
    )

    section_header("Download Reports")

    _report_file = st.session_state.get("wizard_report_file")
    _patch_file  = st.session_state.get("wizard_patch_file")
    _dep_file    = os.path.join("output", "dependency_summary.json")

    dl_c1, dl_c2, dl_c3 = st.columns(3)

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

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

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

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    _ca, _cb, _ = st.columns([1, 1, 3])
    with _ca:
        if st.button("← Back to Review", use_container_width=True):
            st.session_state["wizard_step"] = 3
            st.rerun()
    with _cb:
        if st.button("🔄 Analyze New Repository", use_container_width=True):
            for k in ["wizard_step","last_analysis_jobs","readiness_score","effort_estimate",
                      "auto_fix_recs","wizard_report_file","wizard_patch_file",
                      "wizard_uploaded_file_data","wizard_uploaded_file_name",
                      "_analysis_complete"]:
                st.session_state.pop(k, None)
            st.rerun()
