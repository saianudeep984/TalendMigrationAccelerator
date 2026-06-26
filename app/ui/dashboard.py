"""
Executive Dashboard — compact 5-KPI layout.
Shows: Jobs · Status · Automation · Hours · Risk
"""

import os

import streamlit as st

from app.analyzers.readiness_scorer import score_to_rag as _score_to_rag

def _goto_settings(section: str, key: str) -> None:
    """Render a compact link button that navigates to a specific Settings section."""
    if st.button(f"⚙️ Edit in Settings → {section}", key=key, use_container_width=True):
        from app.ui.design_system_v2 import _NAV_PAGES
        _settings_idx = next(
            (i for i, (k, _) in enumerate(_NAV_PAGES) if k == "settings"), 8
        )
        st.session_state["settings_section"] = section
        st.session_state["_nav_idx2"] = _settings_idx
        st.session_state["_advanced_page"] = None
        st.rerun()



def _cloud_rag(cr: dict) -> str:
    """Get RAG status from a cloud_readiness dict.
    calculate_cloud_readiness() emits 'readiness': HIGH/MEDIUM/LOW with an
    inverted 'rag' field (GREEN=worst). Map on readiness tier first so
    GREEN=ready, AMBER=warning, RED=blocked stays consistent across the app.
    """
    if "readiness" in cr:
        return {"HIGH": "GREEN", "MEDIUM": "AMBER", "LOW": "RED"}.get(cr.get("readiness"), "AMBER")
    if "score" in cr:
        return _score_to_rag(cr.get("score", 0))
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    return "AMBER"

import pandas as pd
import plotly.express as px

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


# ── CSS ───────────────────────────────────────────────────────────────────────
def _css() -> None:
    st.markdown(
        """
        <style>
        /* kill streamlit default top padding */
        .block-container{padding-top:1rem!important;padding-bottom:.75rem!important}
        section[data-testid="stSidebar"] .block-container{padding-top:1rem!important}

        /* 5-KPI strip — max 96px tall */
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
        .kpi-lbl{
            font-size:8px;font-weight:800;color:#64748b;
            text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px;
        }
        .kpi-val{
            font-size:28px;font-weight:900;line-height:1;
            color:var(--kc,#1d4ed8);white-space:nowrap;
        }
        .tma-kpi-card:nth-of-type(5) .tma-kpi-value{
            display:inline-block;padding:2px 12px;border-radius:999px;
            background:var(--kc,#1d4ed8);color:#fff;font-size:16px;
        }
        .kpi-sub{
            font-size:10px;color:#94a3b8;margin-top:3px;
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
        }

        /* tighten expander headers */
        .streamlit-expanderHeader{padding:6px 12px!important;font-size:13px!important}
        div[data-testid="stExpander"]{margin-bottom:6px!important}

        /* compact radio pills */
        div[role="radiogroup"]{gap:5px!important}
        div[role="radiogroup"] label{
            padding:3px 9px!important;min-height:26px!important;
            border-radius:999px;border:1px solid #dbe3ef;background:#fff;
        }

        /* compact st.metric */
        div[data-testid="metric-container"]{padding:0!important}
        div[data-testid="metric-container"] label{font-size:11px!important}
        div[data-testid="metric-container"] [data-testid="stMetricValue"]{font-size:18px!important}
        div[data-testid="metric-container"] [data-testid="stMetricDelta"]{font-size:10px!important}

        @media(max-width:900px){.kpi-strip{grid-template-columns:repeat(3,1fr)}}
        @media(max-width:600px){.kpi-strip{grid-template-columns:1fr 1fr}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _kpi(label, value, sub="", color="#1d4ed8"):
    st.markdown(
        f'<div class="kpi" style="--kc:{color}">'
        f'<div class="kpi-lbl">{label}</div>'
        f'<div class="kpi-val">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def render_executive_dashboard():
    apply_wizard_theme()
    _css()

    from app.ui.design_system_v2 import page_header
    page_header("📊", "Executive Dashboard", "KPIs · RAG · Readiness · Migration Economics")

    if "last_analysis_jobs" not in st.session_state:
        empty_state_card("No repository loaded", "Upload your Talend ZIP on the Home page first.", "warning")
        return

    all_jobs   = st.session_state["last_analysis_jobs"]
    readiness  = st.session_state.get("readiness_score", {})
    effort     = st.session_state.get("effort_estimate", {})
    java_risk  = st.session_state.get("java_risk_analysis", {})
    routines   = st.session_state.get("routine_analysis", {})
    joblets    = st.session_state.get("joblet_analysis", {})
    deprecated = st.session_state.get("deprecated_rows", [])
    custom     = st.session_state.get("custom_analysis", {})

    if not all_jobs:
        empty_state_card("No jobs found", "Run repository analysis again to populate the executive dashboard.", "warning")
        return

    # ── Derived values — bound from the ExecutiveDashboard model ──────────────
    from app.analyzers.models import ExecutiveDashboard

    dashboard_model = ExecutiveDashboard.from_session_data(
        all_jobs=all_jobs,
        readiness=readiness,
        effort=effort,
        routines=routines,
        joblets=joblets,
    )
    dm = dashboard_model.to_dict()

    total       = dm["totalJobs"]
    analyzed_jobs = dm["analyzedJobs"]
    ready_jobs  = dm["readyJobs"]
    warning_jobs = dm["warningJobs"]
    failed_jobs = dm["failedJobs"]
    total_comp  = dm["totalComponents"]
    overall     = dm["cloudReadinessStatus"]
    auto_pct    = dm["automationPct"]
    est_hours   = dm["estimatedHours"] or "—"
    est_weeks   = dm["estimatedWeeks"]
    high_risk   = dm["highRiskCount"]
    risk_label  = dm["riskLabel"]

    # ── Migration Readiness Score — bound from MigrationReadinessScoreCalculator ──
    from app.analyzers.migration_readiness_score import calculate_migration_readiness_score

    mrs_model = calculate_migration_readiness_score(
        all_jobs=all_jobs,
        custom_analysis=custom,
        deprecated_rows=deprecated,
    )
    mrs = mrs_model.to_dict()
    mrs_score = mrs["overallScore"]
    mrs_rag   = mrs["overallRag"]
    mrs_status = mrs["status"]

    # ── 5 KPIs — bound to the ExecutiveDashboard model ─────────────────────────
    drill_filter = ExecutiveDashboardCard(dashboard_model, mrs)

    # ── Qlik-Ready KPI card ───────────────────────────────────────────────────
    _qlik_results = st.session_state.get("qlik_readiness")
    if _qlik_results is None:
        try:
            from app.analyzers.qlik_readiness_analyzer import analyze_qlik_readiness
            _qlik_results = analyze_qlik_readiness(all_jobs)
            st.session_state["qlik_readiness"] = _qlik_results
        except Exception:
            _qlik_results = []
    _qlik_native_count = sum(1 for r in (_qlik_results or []) if r.get("qlik_path") == "QLIK_NATIVE")
    if st.button(
        f"🔵 Talend-Ready Jobs: {_qlik_native_count}  →  View Talend Readiness",
        key="exec_qlik_ready_card",
        use_container_width=True,
    ):
        # Talend Readiness lives in the Command Center tab — navigate there
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
                                        fromlist=["analyze_java_risks"]).analyze_java_risks(all_jobs),
                     ()),
                    ("routine_analysis",
                     lambda: __import__("app.tiap.profiling.routine_profiler",
                                        fromlist=["RoutineProfiler"]).RoutineProfiler().profile(all_jobs, _repo),
                     ()),
                    ("joblet_analysis",
                     lambda: __import__("app.tiap.profiling.joblet_profiler",
                                        fromlist=["JobletProfiler"]).JobletProfiler().profile(all_jobs),
                     ()),
                ]:
                    try:
                        st.session_state[key] = fn()
                    except Exception as e:
                        st.session_state[key] = {}
            st.rerun()

    # Detail expanders
    with st.expander(f"📋 Job Portfolio ({total} jobs)", expanded=False):
        rows = []
        for j in all_jobs:
            rows.append({
                "Job":          j["job_data"]["job_name"],
                "Components":   len(j["job_data"]["components"]),
                "Complexity":   j.get("estimation", {}).get("complexity", "—"),
                "Cloud Readiness": _cloud_rag(j["cloud_readiness"]),
                "Est. Hours":   j.get("estimation", {}).get("estimated_hours", "—"),
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
            st.caption("Migration Readiness Score is a portfolio-level metric — see the breakdown below.")
        if drill_filter:
            st.caption(f"Filtered by KPI: **{drill_filter}** ({len(job_df)} of {total} jobs)")
        styled_dataframe(job_df, "executive_job_portfolio", width="stretch", hide_index=True)
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

    with st.expander("📄 Export Executive Summary (PDF)", expanded=False):
        kpi_summary_df = pd.DataFrame([
            {"KPI": "Total Jobs", "Value": str(total), "Detail": f"{total_comp} components"},
            {"KPI": "Analyzed Jobs", "Value": str(analyzed_jobs), "Detail": f"of {total} jobs"},
            {"KPI": "Ready Jobs", "Value": str(ready_jobs), "Detail": "cloud-ready (GREEN)"},
            {"KPI": "Warning Jobs", "Value": str(warning_jobs), "Detail": "needs review (AMBER)"},
            {"KPI": "High Risk Jobs", "Value": str(high_risk), "Detail": "HIGH/CRITICAL findings"},
            {"KPI": "Failed Jobs", "Value": str(failed_jobs), "Detail": "blocked (RED)"},
            {"KPI": "Cloud Readiness Status", "Value": overall, "Detail": "GREEN Low Effort / AMBER Medium Effort / RED High Effort"},
            {"KPI": "Automation", "Value": f"{auto_pct}%", "Detail": "auto-migratable"},
            {"KPI": "Hours", "Value": str(est_hours), "Detail": f"{est_weeks} wks"},
            {"KPI": "Risk", "Value": str(risk_label), "Detail": f"{high_risk} high/critical"},
            {"KPI": "Migration Readiness Score", "Value": f"{mrs_score}%", "Detail": f"{mrs_rag} — {mrs_status}"},
        ])
        styled_dataframe(kpi_summary_df, "executive_kpi_summary", width="stretch", hide_index=True)

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
        styled_dataframe(risk_df, "executive_risk_table", width="stretch", hide_index=True)

        readiness_df = pd.DataFrame([
            {"Metric": "Cloud Readiness Status", "Value": overall}
        ])
        styled_dataframe(readiness_df, "executive_readiness_metrics", width="stretch", hide_index=True)

        pdf_download_button(
            "Executive Summary",
            [
                ("KPI Summary", kpi_summary_df),
                ("Risk Table", risk_df),
                ("Readiness Metrics", readiness_df),
            ],
            "executive_summary",
            "Executive_Summary.pdf",
        )

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
            st.download_button(
                "⬇️ Download Executive PDF",
                data=st.session_state["_exec_pdf_bytes"],
                file_name=f"TMA_Executive_Assessment_{client_name or 'Client'}.pdf",
                mime="application/pdf",
                key="exec_pdf_download",
                use_container_width=True,
            )

    with st.expander("☕ Java Risk", expanded=False):
        if java_risk and java_risk.get("jobs"):
            st.caption(f"Risk status: {java_risk.get('risk_level', 'REVIEW')}")
            for jr in java_risk.get("jobs", [])[:15]:
                st.markdown(f"**{jr.get('job_name','?')}** — {jr.get('risk_level','?')} · {jr.get('reason','')}")
        else:
            st.caption("No Java risk data — run analysis above.")
        _goto_settings("Migration Risk", "exec_java_risk_settings")

    with st.expander("🔀 Business Flow", expanded=False):
        from app.ui.preflight_dashboard import render_business_flow
        render_business_flow()

    with st.expander("💰 Migration Economics", expanded=False):
        econ_df = pd.DataFrame([
            {"Metric": "Auto-Migratable", "Value": f"{auto_pct}%"},
            {"Metric": "Manual Required", "Value": f"{effort.get('manual_pct', 0) if effort else 0}%"},
            {"Metric": "Estimated Hours", "Value": str(est_hours)},
            {"Metric": "Estimated Days", "Value": str(effort.get("estimated_days", "—") if effort else "—")},
            {"Metric": "Estimated Weeks", "Value": str(est_weeks)},
            {"Metric": "High/Critical Risk Jobs", "Value": str(high_risk)},
            {"Metric": "Cloud Readiness Status", "Value": overall},
        ])
        styled_dataframe(econ_df, "executive_migration_economics", width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        with c1: _goto_settings("Effort Estimation", "exec_econ_effort_settings")
        with c2: _goto_settings("Simulation Sandbox", "exec_econ_sim_settings")

    with st.expander("🧭 Migration Readiness Score", expanded=(drill_filter == "Migration Readiness Score")):
        st.caption(f"Overall: **{mrs_score}%** ({mrs_rag}) — {mrs_status}")
        mrs_df = pd.DataFrame([
            {"Dimension": d["dimension"], "Score": f"{d['score']}%", "RAG": d["rag"],
             "Weight": f"{int(d['weight']*100)}%", "Detail": d["detail"]}
            for d in mrs["dimensions"]
        ])
        styled_dataframe(mrs_df, "executive_migration_readiness_score", width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        with c1: _goto_settings("Assessment Rules", "exec_mrs_rules_settings")
        with c2: _goto_settings("Complexity Scoring", "exec_mrs_complexity_settings")

    with st.expander("📦 Routines & Joblets", expanded=False):
        rc = routines.get("total_routines", "—") if routines else "—"
        jc = joblets.get("total_joblets", "—") if joblets else "—"
        st.caption(f"Custom routines: **{rc}** · Joblets: **{jc}**")
        if routines and routines.get("routines"):
            styled_dataframe(
                pd.DataFrame(routines["routines"]),
                "executive_routines",
                width="stretch",
                hide_index=True,
            )

    with st.expander("⚠️ Unsupported Components", expanded=False):
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

    with st.expander("🌳 Job Hierarchy", expanded=False):
        render_job_hierarchy_tree(all_jobs)

    # Report Pack
    with st.expander("📥 Report Pack", expanded=False):
        from app.tiap.documentation.report_pack_generator import (
            REPORT_PACK_FILENAME, REPORT_PACK_SESSION_KEY, build_report_pack)
        from app.ai.repository_ai_context import REPOSITORY_AI_CONTEXT_SESSION_KEY
        from app.tiap.documentation.template_manager import (
            DEFAULT_TEMPLATE_PATH, TEMPLATE_SESSION_KEY,
            active_template_label,
            restore_default_template, save_custom_template)

        if TEMPLATE_SESSION_KEY not in st.session_state:
            st.session_state[TEMPLATE_SESSION_KEY] = DEFAULT_TEMPLATE_PATH
        active_template = st.session_state[TEMPLATE_SESSION_KEY]

        tc1, tc2 = st.columns(2)
        with tc1:
            if st.button("Use Default Template", width="stretch", key="tmpl_default"):
                st.session_state[TEMPLATE_SESSION_KEY] = DEFAULT_TEMPLATE_PATH
                active_template = DEFAULT_TEMPLATE_PATH
        with tc2:
            if st.button("Restore Default Template", width="stretch", key="tmpl_restore"):
                st.session_state[TEMPLATE_SESSION_KEY] = restore_default_template()
                active_template = st.session_state[TEMPLATE_SESSION_KEY]

        st.caption(f"Active: {active_template_label(active_template)}")
        uploaded_tmpl = st.file_uploader("Upload Custom Template (.docx)", type=["docx"],
                                         key="custom_tmpl_upload")
        if uploaded_tmpl:
            cp = save_custom_template(uploaded_tmpl)
            st.session_state[TEMPLATE_SESSION_KEY] = cp
            active_template = cp

        generated_pack = st.session_state.get(REPORT_PACK_SESSION_KEY)
        if st.button("Generate AI Pack", type="primary", width="stretch", key="gen_pack"):
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
                        st.download_button(label, data=data, file_name=fname,
                                           mime=mime, width="stretch")
                    else:
                        st.button(label, disabled=True, width="stretch")


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
    styled_dataframe(pd.DataFrame(rows), "legacy_dashboard_summary", width="stretch")
