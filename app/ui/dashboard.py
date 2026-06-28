"""
Executive Dashboard — left-panel section selector + right-panel content.
"""

import os
import pandas as pd
import streamlit as st

from app.analyzers.readiness_scorer import score_to_rag as _score_to_rag


def _goto_settings(section: str, key: str) -> None:
    if st.button(f"⚙️ Edit → {section}", key=key, use_container_width=True):
        from app.ui.design_system_v2 import _NAV_PAGES
        _settings_idx = next(
            (i for i, (k, _) in enumerate(_NAV_PAGES) if k == "settings"), 8
        )
        st.session_state["settings_section"] = section
        st.session_state["_nav_idx2"] = _settings_idx
        st.session_state["_advanced_page"] = None
        st.rerun()


def _cloud_rag(cr: dict) -> str:
    if "readiness" in cr:
        return {"HIGH": "GREEN", "MEDIUM": "AMBER", "LOW": "RED"}.get(cr.get("readiness"), "AMBER")
    if "score" in cr:
        return _score_to_rag(cr.get("score", 0))
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    return "AMBER"


from app.ui.design_system_v2 import (
    apply_wizard_theme,
    empty_state_card,
    ExecutiveDashboardCard,
    pdf_download_button,
    render_complexity_distribution_chart,
    render_job_hierarchy_tree,
    render_unsupported_components_report,
    styled_dataframe,
)
from app.ui.score_explainer import render_score_explainer
from app.reports.executive_pdf_generator import generate_executive_pdf


def _css() -> None:
    st.markdown("""
    <style>
    .block-container{padding-top:1rem!important;padding-bottom:.75rem!important}
    section[data-testid="stSidebar"] .block-container{padding-top:1rem!important}

    .kpi-strip{
        display:grid;
        grid-template-columns:repeat(5,minmax(0,1fr));
        gap:8px;margin:0 0 8px;
    }
    .kpi{
        background:#fff;border:1px solid #dbe3ef;border-radius:7px;
        padding:8px 10px 6px;max-height:96px;overflow:hidden;
        border-top:3px solid var(--kc,#1d4ed8);
        box-shadow:0 1px 2px rgba(15,23,42,.05);
    }
    .kpi-lbl{font-size:8px;font-weight:800;color:#64748b;
        text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px;}
    .kpi-val{font-size:28px;font-weight:900;line-height:1;
        color:var(--kc,#1d4ed8);white-space:nowrap;}
    .kpi-sub{font-size:10px;color:#94a3b8;margin-top:3px;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

    div[data-testid="metric-container"]{padding:0!important}
    div[data-testid="metric-container"] label{font-size:11px!important}
    div[data-testid="metric-container"] [data-testid="stMetricValue"]{font-size:18px!important}
    div[data-testid="metric-container"] [data-testid="stMetricDelta"]{font-size:10px!important}

    /* left panel radio nav — compact, no scroll */
    div[data-testid="stRadio"] > label { display:none !important; }
    div[data-testid="stRadio"] > div {
        gap: 2px !important;
        display: flex !important;
        flex-direction: column !important;
    }
    div[data-testid="stRadio"] > div > label {
        padding: 6px 10px !important;
        border-radius: 6px !important;
        border: 1px solid #e2e8f0 !important;
        background: #f8fafc !important;
        font-size: 12px !important;
        cursor: pointer !important;
        line-height: 1.3 !important;
        min-height: unset !important;
        transition: background 0.12s, border-color 0.12s;
    }
    div[data-testid="stRadio"] > div > label:hover {
        background: #eff6ff !important;
        border-color: #bfdbfe !important;
    }
    /* hide the radio circle dot — make it look like a menu */
    div[data-testid="stRadio"] > div > label > div:first-child {
        display: none !important;
    }

    /* right panel divider */
    .exec-section-title {
        font-size: 18px;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 4px;
    }

    @media(max-width:900px){.kpi-strip{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:600px){.kpi-strip{grid-template-columns:1fr 1fr}}
    </style>
    """, unsafe_allow_html=True)


def _kpi(label, value, sub="", color="#1d4ed8"):
    st.markdown(
        f'<div class="kpi" style="--kc:{color}">'
        f'<div class="kpi-lbl">{label}</div>'
        f'<div class="kpi-val">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Section renderers ─────────────────────────────────────────────────────────

def _render_job_portfolio(all_jobs, total, drill_filter, effort):
    rows = []
    for j in all_jobs:
        rows.append({
            "Job":             j["job_data"]["job_name"],
            "Components":      len(j["job_data"]["components"]),
            "Complexity":      j.get("estimation", {}).get("complexity", "—"),
            "Cloud Readiness": _cloud_rag(j["cloud_readiness"]),
            "Est. Hours":      j.get("estimation", {}).get("estimated_hours", "—"),
        })
    job_df = pd.DataFrame(rows)
    if drill_filter == "Risk":
        job_df = job_df[job_df["Complexity"].isin(["HIGH", "CRITICAL"])]
    elif drill_filter == "Automation":
        job_df = job_df[job_df["Complexity"].isin(["LOW", "MEDIUM"])]
    elif drill_filter == "Hours":
        job_df = job_df.sort_values("Est. Hours", ascending=False)
    elif drill_filter == "Analyzed Jobs":
        job_df = job_df[job_df["Complexity"] != "—"]
    elif drill_filter == "Ready Jobs":
        job_df = job_df[job_df["Cloud Readiness"] == "GREEN"]
    elif drill_filter == "Warning Jobs":
        job_df = job_df[job_df["Cloud Readiness"] == "AMBER"]
    elif drill_filter == "High Risk Jobs":
        job_df = job_df[job_df["Complexity"].isin(["HIGH", "CRITICAL"])]
    elif drill_filter == "Failed Jobs":
        job_df = job_df[job_df["Cloud Readiness"] == "RED"]
    elif drill_filter == "Migration Readiness Score":
        st.caption("Migration Readiness Score is a portfolio-level metric.")
    if drill_filter:
        st.caption(f"Filtered by KPI: **{drill_filter}** ({len(job_df)} of {total} jobs)")
    styled_dataframe(job_df, "executive_job_portfolio", use_container_width=True, hide_index=True)
    _job_name_set = set(job_df["Job"].tolist())
    for _idx, _j in enumerate(all_jobs):
        _jname = _j["job_data"]["job_name"]
        if _jname in _job_name_set:
            with st.expander(f"🔍 {_jname} — why this score?", expanded=False):
                render_score_explainer(_j, key_suffix=f"_{_idx}")
    pdf_download_button("Executive Job Portfolio", [("Jobs", job_df)], "executive_job_portfolio", "Executive_Job_Portfolio.pdf")
    c1, c2 = st.columns(2)
    with c1: _goto_settings("Cloud Readiness", "exec_portfolio_cloud_settings")
    with c2: _goto_settings("Complexity Scoring", "exec_portfolio_complexity_settings")


def _render_portfolio_overview(total, auto_pct, effort):
    _hourly_rate = 50.0
    _total_hours_num = effort.get("estimated_hours", 0) if effort else 0
    _est_cost = _total_hours_num * _hourly_rate
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Jobs", total)
    with c2: st.metric("Total Hours", _total_hours_num if _total_hours_num else "—")
    with c3: st.metric("Automation", f"{auto_pct}%")
    with c4: st.metric("Est. Cost", f"${_est_cost:,.0f}" if _total_hours_num else "—")
    st.caption("Cost estimate at default $50/hr rate.")
    _goto_settings("Effort Estimation", "exec_portfolio_overview_settings")


def _render_export_pdf(all_jobs, total, total_comp, analyzed_jobs, ready_jobs, warning_jobs,
                       high_risk, failed_jobs, overall, auto_pct, est_hours, est_weeks,
                       risk_label, mrs_score, mrs_rag, mrs_status):
    kpi_summary_df = pd.DataFrame([
        {"KPI": "Total Jobs",             "Value": str(total),         "Detail": f"{total_comp} components"},
        {"KPI": "Analyzed Jobs",          "Value": str(analyzed_jobs), "Detail": f"of {total} jobs"},
        {"KPI": "Ready Jobs",             "Value": str(ready_jobs),    "Detail": "cloud-ready (GREEN)"},
        {"KPI": "Warning Jobs",           "Value": str(warning_jobs),  "Detail": "needs review (AMBER)"},
        {"KPI": "High Risk Jobs",         "Value": str(high_risk),     "Detail": "HIGH/CRITICAL findings"},
        {"KPI": "Failed Jobs",            "Value": str(failed_jobs),   "Detail": "blocked (RED)"},
        {"KPI": "Cloud Readiness Status", "Value": overall,            "Detail": "GREEN/AMBER/RED"},
        {"KPI": "Automation",             "Value": f"{auto_pct}%",     "Detail": "auto-migratable"},
        {"KPI": "Hours",                  "Value": str(est_hours),     "Detail": f"{est_weeks} wks"},
        {"KPI": "Risk",                   "Value": str(risk_label),    "Detail": f"{high_risk} high/critical"},
        {"KPI": "Migration Readiness",    "Value": f"{mrs_score}%",    "Detail": f"{mrs_rag} — {mrs_status}"},
    ])
    styled_dataframe(kpi_summary_df, "executive_kpi_summary", use_container_width=True, hide_index=True)
    risk_rows = [{
        "Job": j["job_data"]["job_name"],
        "Complexity": j.get("estimation", {}).get("complexity", "—"),
        "Cloud Readiness": _cloud_rag(j["cloud_readiness"]),
        "High/Critical Findings": sum(
            1 for r in j.get("enterprise_risk_report", []) if r.get("risk") in ("HIGH", "CRITICAL")
        ),
    } for j in all_jobs]
    risk_df = pd.DataFrame(risk_rows)
    risk_df = risk_df[risk_df["Complexity"].isin(["HIGH", "CRITICAL"]) | (risk_df["High/Critical Findings"] > 0)]
    styled_dataframe(risk_df, "executive_risk_table", use_container_width=True, hide_index=True)
    readiness_df = pd.DataFrame([{"Metric": "Cloud Readiness Status", "Value": overall}])
    styled_dataframe(readiness_df, "executive_readiness_metrics", use_container_width=True, hide_index=True)
    pdf_download_button("Executive Summary",
        [("KPI Summary", kpi_summary_df), ("Risk Table", risk_df), ("Readiness Metrics", readiness_df)],
        "executive_summary", "Executive_Summary.pdf")
    st.markdown("---")
    st.markdown("**📄 Branded Executive PDF**")
    client_name = st.text_input("Client name", key="exec_pdf_client_name", placeholder="e.g. Henry Schein")
    logo_file = st.file_uploader("Client logo (optional)", type=["png", "jpg"], key="exec_pdf_logo")
    if st.button("📄 Generate Branded PDF", key="exec_pdf_generate", use_container_width=True, type="primary"):
        with st.spinner("Generating…"):
            logo_bytes = logo_file.read() if logo_file else None
            pdf_bytes = generate_executive_pdf(
                session_state=st.session_state,
                client_name=client_name or "Client",
                logo_path=logo_bytes,
            )
        st.session_state["_exec_pdf_bytes"] = pdf_bytes
    if st.session_state.get("_exec_pdf_bytes"):
        st.download_button("⬇️ Download Executive PDF",
            data=st.session_state["_exec_pdf_bytes"],
            file_name=f"TMA_Executive_Assessment_{client_name or 'Client'}.pdf",
            mime="application/pdf", key="exec_pdf_download", use_container_width=True)


def _render_java_risk(java_risk):
    if java_risk and java_risk.get("jobs"):
        st.caption(f"Risk status: {java_risk.get('risk_level', 'REVIEW')}")
        for jr in java_risk.get("jobs", [])[:15]:
            st.markdown(f"**{jr.get('job_name','?')}** — {jr.get('risk_level','?')} · {jr.get('reason','')}")
    else:
        st.caption("No Java risk data — run analysis first.")
    _goto_settings("Migration Risk", "exec_java_risk_settings")


def _render_business_flow():
    from app.ui.preflight_dashboard import render_business_flow
    render_business_flow()
    _goto_settings("Migration Risk", "exec_business_flow_settings")


def _render_migration_economics(auto_pct, effort, est_hours, est_weeks, high_risk, overall):
    econ_df = pd.DataFrame([
        {"Metric": "Auto-Migratable",        "Value": f"{auto_pct}%"},
        {"Metric": "Manual Required",         "Value": f"{effort.get('manual_pct', 0) if effort else 0}%"},
        {"Metric": "Estimated Hours",         "Value": str(est_hours)},
        {"Metric": "Estimated Days",          "Value": str(effort.get("estimated_days", "—") if effort else "—")},
        {"Metric": "Estimated Weeks",         "Value": str(est_weeks)},
        {"Metric": "High/Critical Risk Jobs", "Value": str(high_risk)},
        {"Metric": "Cloud Readiness Status",  "Value": overall},
    ])
    styled_dataframe(econ_df, "executive_migration_economics", use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1: _goto_settings("Effort Estimation", "exec_econ_effort_settings")
    with c2: _goto_settings("Simulation Sandbox", "exec_econ_sim_settings")


def _render_readiness_score(mrs, mrs_score, mrs_rag, mrs_status):
    st.caption(f"Overall: **{mrs_score}%** ({mrs_rag}) — {mrs_status}")
    mrs_df = pd.DataFrame([
        {"Dimension": d["dimension"], "Score": f"{d['score']}%", "RAG": d["rag"],
         "Weight": f"{int(d['weight']*100)}%", "Detail": d["detail"]}
        for d in mrs["dimensions"]
    ])
    styled_dataframe(mrs_df, "executive_migration_readiness_score", use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1: _goto_settings("Assessment Rules", "exec_mrs_rules_settings")
    with c2: _goto_settings("Complexity Scoring", "exec_mrs_complexity_settings")


def _render_migration_advisor():
    try:
        from app.ui.migration_advisor_dashboard import build_migration_advisor_dashboard
        from app.parser.project_classifier import ProjectType
        _adv_source = st.session_state.get("wizard_source_version", "Unknown")
        _adv_qlik   = st.session_state.get("wizard_qlik_mode", False)
        _adv_studio = st.session_state.get("wizard_open_studio", False)
        if _adv_qlik:
            _adv_ptype = ProjectType.CLOUD
        elif _adv_studio:
            _adv_ptype = ProjectType.OPEN_STUDIO
        else:
            _adv_ptype = ProjectType.ENTERPRISE
        _adv_data = build_migration_advisor_dashboard(project_type=_adv_ptype, source_version=_adv_source)
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Project Type", _adv_data["projectType"])
        with c2: st.metric("Source",        _adv_data["sourceVersion"])
        with c3: st.metric("Target",        _adv_data["targetVersion"] or "N/A")
        _actions = _adv_data.get("recommendedActions", [])
        if _actions:
            st.caption("**Next steps**")
            for _i, _step in enumerate(_actions[:2], 1):
                st.markdown(f"{_i}. {_step}")
        else:
            st.caption(_adv_data.get("rationale", "Run analysis to generate recommendations."))
    except Exception as _adv_err:
        st.caption(f"Advisor unavailable — run analysis first. ({_adv_err})")
    _goto_settings("Migration Risk", "exec_migration_advisor_settings")


def _render_routines(routines, joblets):
    rc = routines.get("total_routines", "—") if routines else "—"
    jc = joblets.get("total_joblets", "—") if joblets else "—"
    st.caption(f"Custom routines: **{rc}** · Joblets: **{jc}**")
    if routines and routines.get("routines"):
        styled_dataframe(pd.DataFrame(routines["routines"]), "executive_routines", use_container_width=True, hide_index=True)
    _goto_settings("Complexity Scoring", "exec_routines_settings")


def _render_unsupported(all_jobs):
    _uc = st.session_state.get("unsupported_component_report")
    if not _uc:
        if st.button("▶ Scan Unsupported Components", type="primary", key="btn_run_unsupported"):
            with st.spinner("Scanning…"):
                try:
                    from app.analyzers.unsupported_component_analyzer import analyze_unsupported_components
                    _uc = analyze_unsupported_components(
                        all_jobs, routine_analysis=st.session_state.get("routine_analysis"))
                    st.session_state["unsupported_component_report"] = _uc
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    if _uc:
        render_unsupported_components_report(_uc)
    _goto_settings("Migration Risk", "exec_unsupported_settings")


def _render_job_hierarchy(all_jobs):
    render_job_hierarchy_tree(all_jobs)
    _goto_settings("Complexity Scoring", "exec_hierarchy_settings")


def _render_report_pack(all_jobs, effort):
    from app.tiap.documentation.report_pack_generator import (
        REPORT_PACK_FILENAME, REPORT_PACK_SESSION_KEY, build_report_pack)
    from app.ai.repository_ai_context import REPOSITORY_AI_CONTEXT_SESSION_KEY
    from app.tiap.documentation.template_manager import (
        DEFAULT_TEMPLATE_PATH, TEMPLATE_SESSION_KEY,
        active_template_label, restore_default_template, save_custom_template)

    if TEMPLATE_SESSION_KEY not in st.session_state:
        st.session_state[TEMPLATE_SESSION_KEY] = DEFAULT_TEMPLATE_PATH
    active_template = st.session_state[TEMPLATE_SESSION_KEY]

    tc1, tc2 = st.columns(2)
    with tc1:
        if st.button("Use Default Template", use_container_width=True, key="tmpl_default"):
            st.session_state[TEMPLATE_SESSION_KEY] = DEFAULT_TEMPLATE_PATH
            active_template = DEFAULT_TEMPLATE_PATH
    with tc2:
        if st.button("Restore Default Template", use_container_width=True, key="tmpl_restore"):
            st.session_state[TEMPLATE_SESSION_KEY] = restore_default_template()
            active_template = st.session_state[TEMPLATE_SESSION_KEY]

    st.caption(f"Active: {active_template_label(active_template)}")
    uploaded_tmpl = st.file_uploader("Upload Custom Template (.docx)", type=["docx"], key="custom_tmpl_upload")
    if uploaded_tmpl:
        cp = save_custom_template(uploaded_tmpl)
        st.session_state[TEMPLATE_SESSION_KEY] = cp
        active_template = cp

    generated_pack = st.session_state.get(REPORT_PACK_SESSION_KEY)
    if st.button("Generate AI Pack", type="primary", use_container_width=True, key="gen_pack"):
        with st.spinner("Generating…"):
            generated_pack = build_report_pack(
                all_jobs=all_jobs,
                repository_path=st.session_state.get("last_repo_path"),
                output_dir="output",
                effort=effort,
                auto_fix_recs=st.session_state.get("auto_fix_recs"),
                technical_template=st.session_state.get("technical_doc_template"),
                report_template_path=active_template,
                test_cases=_format_test_cases_for_dash(st.session_state.get("test_cases")),
                repository_ai_context=st.session_state.get(REPOSITORY_AI_CONTEXT_SESSION_KEY),
            )
            st.session_state[REPORT_PACK_SESSION_KEY] = generated_pack
            for k, fp in [("_rp_docx_bytes", generated_pack.get("docx_path")),
                           ("_rp_pdf_bytes",  generated_pack.get("pdf_path")),
                           ("_rp_html_bytes", generated_pack.get("html_path"))]:
                if fp and os.path.exists(fp):
                    with open(fp, "rb") as f:
                        st.session_state[k] = f.read()
        st.success(f"Generated {REPORT_PACK_FILENAME}")

    if generated_pack:
        d1, d2, d3 = st.columns(3)
        for col, label, key_s, fname, mime in [
            (d1, "⬇ DOCX", "_rp_docx_bytes", REPORT_PACK_FILENAME,
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (d2, "⬇ PDF",  "_rp_pdf_bytes",  "Complete_Assessment.pdf", "application/pdf"),
            (d3, "⬇ HTML", "_rp_html_bytes", "Complete_Assessment.html", "text/html"),
        ]:
            with col:
                data = st.session_state.get(key_s)
                if data:
                    st.download_button(label, data=data, file_name=fname, mime=mime, use_container_width=True)
                else:
                    st.button(label, disabled=True, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────
def render_executive_dashboard():
    apply_wizard_theme()
    _css()

    from app.ui.design_system_v2 import page_header
    page_header("📊", "Executive Dashboard", "KPIs · RAG · Readiness · Migration Economics")

    if "last_analysis_jobs" not in st.session_state:
        empty_state_card("No repository loaded", "Upload your Talend ZIP on the Home page first.", "warning")
        return

    all_jobs  = st.session_state["last_analysis_jobs"]
    readiness = st.session_state.get("readiness_score", {})
    effort    = st.session_state.get("effort_estimate", {})
    java_risk = st.session_state.get("java_risk_analysis", {})
    routines  = st.session_state.get("routine_analysis", {})
    joblets   = st.session_state.get("joblet_analysis", {})
    deprecated= st.session_state.get("deprecated_rows", [])
    custom    = st.session_state.get("custom_analysis", {})

    if not all_jobs:
        empty_state_card("No jobs found", "Run repository analysis again.", "warning")
        return

    from app.analyzers.models import ExecutiveDashboard
    dashboard_model = ExecutiveDashboard.from_session_data(
        all_jobs=all_jobs, readiness=readiness, effort=effort,
        routines=routines, joblets=joblets,
    )
    dm = dashboard_model.to_dict()

    total         = dm["totalJobs"]
    analyzed_jobs = dm["analyzedJobs"]
    ready_jobs    = dm["readyJobs"]
    warning_jobs  = dm["warningJobs"]
    failed_jobs   = dm["failedJobs"]
    total_comp    = dm["totalComponents"]
    overall       = dm["cloudReadinessStatus"]
    auto_pct      = dm["automationPct"]
    est_hours     = dm["estimatedHours"] or "—"
    est_weeks     = dm["estimatedWeeks"]
    high_risk     = dm["highRiskCount"]
    risk_label    = dm["riskLabel"]

    from app.analyzers.migration_readiness_score import calculate_migration_readiness_score
    mrs_model = calculate_migration_readiness_score(
        all_jobs=all_jobs, custom_analysis=custom, deprecated_rows=deprecated)
    mrs       = mrs_model.to_dict()
    mrs_score = mrs["overallScore"]
    mrs_rag   = mrs["overallRag"]
    mrs_status= mrs["status"]

    # KPI strip
    drill_filter = ExecutiveDashboardCard(dashboard_model, mrs)

    # Qlik button
    _qlik_results = st.session_state.get("qlik_readiness")
    if _qlik_results is None:
        try:
            from app.analyzers.qlik_readiness_analyzer import analyze_qlik_readiness
            _qlik_results = analyze_qlik_readiness(all_jobs)
            st.session_state["qlik_readiness"] = _qlik_results
        except Exception:
            _qlik_results = []
    _qlik_native_count = sum(1 for r in (_qlik_results or []) if r.get("qlik_path") == "QLIK_NATIVE")
    if st.button(f"🔵 Talend-Ready Jobs: {_qlik_native_count}  →  View Talend Readiness",
                 key="exec_qlik_ready_card", use_container_width=True):
        from app.ui.design_system_v2 import _NAV_PAGES
        _cc_idx = next((i for i, (k, _) in enumerate(_NAV_PAGES) if k == "command_center"), 1)
        st.session_state["_nav_idx2"] = _cc_idx
        st.session_state["_advanced_page"] = None
        st.rerun()

    # Pending analyses
    any_pending = not java_risk or not routines or not joblets
    if any_pending:
        if st.button("▶ Run All Pending Analyses", type="primary", key="exec_run_all"):
            _repo = st.session_state.get("last_repo_path", "")
            with st.spinner("Running analyses…"):
                for key, fn, args in [
                    ("java_risk_analysis",
                     lambda: __import__("app.analyzers.java_risk_analyzer",
                                        fromlist=["analyze_java_risks"]).analyze_java_risks(all_jobs), ()),
                    ("routine_analysis",
                     lambda: __import__("app.tiap.profiling.routine_profiler",
                                        fromlist=["RoutineProfiler"]).RoutineProfiler().profile(all_jobs, _repo), ()),
                    ("joblet_analysis",
                     lambda: __import__("app.tiap.profiling.joblet_profiler",
                                        fromlist=["JobletProfiler"]).JobletProfiler().profile(all_jobs), ()),
                ]:
                    try:
                        st.session_state[key] = fn()
                    except Exception as e:
                        st.session_state[key] = {}
            st.rerun()

    st.markdown("---")

    # ── Left panel + Right panel ───────────────────────────────────────────────
    SECTIONS = [
        ("📋 Job Portfolio",          f"📋 Job Portfolio ({total} jobs)"),
        ("📊 Portfolio Overview",     "📊 Portfolio Overview"),
        ("📄 Export PDF",             "📄 Export Executive Summary (PDF)"),
        ("☕ Java Risk",              "☕ Java Risk"),
        ("🔀 Business Flow",          "🔀 Business Flow"),
        ("💰 Migration Economics",    "💰 Migration Economics"),
        ("🧭 Readiness Score",        "🧭 Migration Readiness Score"),
        ("🧭 Migration Advisor",      "🧭 Migration Advisor"),
        ("📦 Routines & Joblets",     "📦 Routines & Joblets"),
        ("⚠️ Unsupported Components", "⚠️ Unsupported Components"),
        ("🌳 Job Hierarchy",          "🌳 Job Hierarchy"),
        ("📥 Report Pack",            "📥 Report Pack"),
    ]
    short_labels = [s[0] for s in SECTIONS]
    full_labels  = [s[1] for s in SECTIONS]

    if "_exec_section" not in st.session_state:
        st.session_state["_exec_section"] = short_labels[0]

    left_col, right_col = st.columns([1, 3], gap="medium")

    with left_col:
        selected = st.radio(
            "Section",
            options=short_labels,
            index=short_labels.index(st.session_state["_exec_section"])
                  if st.session_state["_exec_section"] in short_labels else 0,
            key="exec_section_radio",
            label_visibility="collapsed",
        )
        st.session_state["_exec_section"] = selected

    with right_col:
        full_label = full_labels[short_labels.index(selected)]
        st.markdown(f"### {full_label}")
        st.markdown("---")

        if selected == "📋 Job Portfolio":
            _render_job_portfolio(all_jobs, total, drill_filter, effort)
        elif selected == "📊 Portfolio Overview":
            _render_portfolio_overview(total, auto_pct, effort)
        elif selected == "📄 Export PDF":
            _render_export_pdf(
                all_jobs, total, total_comp, analyzed_jobs, ready_jobs, warning_jobs,
                high_risk, failed_jobs, overall, auto_pct, est_hours, est_weeks,
                risk_label, mrs_score, mrs_rag, mrs_status)
        elif selected == "☕ Java Risk":
            _render_java_risk(java_risk)
        elif selected == "🔀 Business Flow":
            _render_business_flow()
        elif selected == "💰 Migration Economics":
            _render_migration_economics(auto_pct, effort, est_hours, est_weeks, high_risk, overall)
        elif selected == "🧭 Readiness Score":
            _render_readiness_score(mrs, mrs_score, mrs_rag, mrs_status)
        elif selected == "🧭 Migration Advisor":
            _render_migration_advisor()
        elif selected == "📦 Routines & Joblets":
            _render_routines(routines, joblets)
        elif selected == "⚠️ Unsupported Components":
            _render_unsupported(all_jobs)
        elif selected == "🌳 Job Hierarchy":
            _render_job_hierarchy(all_jobs)
        elif selected == "📥 Report Pack":
            _render_report_pack(all_jobs, effort)


def _format_test_cases_for_dash(test_cases) -> str:
    if not test_cases:
        return ""
    if isinstance(test_cases, str):
        return test_cases
    lines = []
    for item in test_cases:
        if isinstance(item, dict):
            tc_id    = item.get("tc_id") or item.get("id") or "Test Case"
            category = item.get("category") or item.get("test_type") or ""
            obj      = item.get("objective") or item.get("expected_result") or ""
            lines.append(f"- {tc_id} {category}: {obj}".strip())
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def show_dashboard(all_jobs):
    """Legacy inline dashboard called from Repository Intake page."""
    st.header("📊 Dashboard Summary")
    if not all_jobs:
        return
    rows = [{
        "Job":        j["job_data"]["job_name"],
        "Components": len(j["job_data"]["components"]),
        "Complexity": j.get("estimation", {}).get("complexity", "—"),
        "Cloud Readiness": _cloud_rag(j["cloud_readiness"]),
        "Est. Hours": j.get("estimation", {}).get("estimated_hours", "—"),
    } for j in all_jobs]
    styled_dataframe(pd.DataFrame(rows), "legacy_dashboard_summary", use_container_width=True)
