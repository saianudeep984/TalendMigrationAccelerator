"""
Pre-Flight Assessment Dashboard
Enterprise Migration Factory — Phase 1 & 2 Features
"""

import streamlit as st

from app.analyzers.readiness_scorer import score_to_rag as _score_to_rag

def _cloud_rag(cr: dict) -> str:
    """Get RAG status from a cloud_readiness dict."""
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    return _score_to_rag(cr.get("score", 0))

import html as html_lib
import pandas as pd
import plotly.express as px

from app.ui.design_system import action_panel, metric_card
from app.ui.design_system_v2 import (
    pdf_download_button,
    rag_metric_card,
    render_clickable_kpi_row,
    render_mermaid_diagram,
    risk_badge,
    section_header as section,
    styled_dataframe,
    render_insights_row,
    render_progress_metric,
)


# ---------------------------------------------------------------
# HELPER: colored badge HTML
# ---------------------------------------------------------------

def _render_mermaid(mermaid_code: str, height: int = 420) -> None:
    """Render a Mermaid-style flowchart diagram, fully offline (no CDN)."""
    render_mermaid_diagram(mermaid_code, height=height)


def _badge(text, color):
    colors = {
        "RED":    "#e53e3e",
        "ORANGE": "#dd6b20",
        "YELLOW": "#d69e2e",
        "GREEN":  "#38a169",
        "BLUE":   "#3182ce",
        "GRAY":   "#718096",
    }
    bg = colors.get(color, "#718096")
    return (
        f'<span style="background:{bg};color:white;padding:2px 8px;'
        f'border-radius:12px;font-size:0.78rem;font-weight:600">{text}</span>'
    )


def _risk_color(risk):
    m = {"CRITICAL": "RED", "HIGH": "ORANGE", "MEDIUM": "YELLOW", "LOW": "GREEN"}
    return m.get(str(risk).upper(), "GRAY")


# ---------------------------------------------------------------
# BUSINESS FLOW DIAGRAM (Mermaid)
# ---------------------------------------------------------------

def render_business_flow():
    """Renders a business-level data flow diagram hiding technical components."""
    mermaid_code = """
graph LR
    A([📥 Source<br/>Systems]) -->|Raw Data| B([✅ Validation<br/>& Profiling])
    B -->|Cleansed Data| C([🔄 Transformation<br/>& Mapping])
    C -->|Enriched Data| D([📊 Aggregation<br/>& Business Rules])
    D -->|Processed Data| E([📤 Target<br/>Systems])
"""
    st.markdown(
        """
        <style>
        .business-flow-label {
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            color: #718096;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        </style>
        <div class="business-flow-label">Business Data Flow</div>
        """,
        unsafe_allow_html=True
    )
    _render_mermaid(mermaid_code, height=320)


# ---------------------------------------------------------------
# 1. Pre-Flight Assessment Dashboard  (OPTIMIZED)
# ---------------------------------------------------------------

def render_preflight_dashboard(all_jobs, custom_analysis, deprecated_rows,
                                readiness_score, effort_estimate):
    # ── Compact global CSS ──────────────────────────────────────
    st.markdown("""
    <style>
    /* Remove default top padding */
    .block-container { padding-top: 52px !important; padding-bottom: 0.5rem !important; }
    /* Compact metric cards */
    [data-testid="metric-container"] {
        background: #1e2433;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 8px 12px !important;
        min-height: unset !important;
        max-height: 90px !important;
    }
    [data-testid="metric-container"] label { font-size: 0.70rem !important; color: #a0aec0; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 1.35rem !important; line-height: 1.2 !important; }
    [data-testid="metric-container"] [data-testid="stMetricDelta"] { display: none; }
    /* Remove banner/header gap */
    header[data-testid="stHeader"] { display: none !important; }
    .stApp > header { display: none !important; }
    /* Tight section spacing */
    hr { margin: 6px 0 !important; border-color: #2d3748 !important; }
    h2, h3 { margin-top: 6px !important; margin-bottom: 4px !important; font-size: 0.95rem !important; }
    /* Compact tabs */
    button[data-baseweb="tab"] { padding: 0.3rem 0.7rem !important; font-size: 0.82rem !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Compute KPIs ────────────────────────────────────────────
    total_jobs = len(all_jobs)
    automation_pct = effort_estimate.get("auto_pct", 0) if effort_estimate else 0
    est_hours = round(effort_estimate.get("estimated_days", 0) * 8, 1) if effort_estimate else 0
    cloud_blockers = sum(
        1 for j in all_jobs if j["cloud_readiness"]["readiness"] == "LOW"
    )
    overall_rag = readiness_score.get("overall", "RED")
    if overall_rag == "GREEN":
        risk_label = "🟢 LOW"
    elif overall_rag == "AMBER":
        risk_label = "🟡 MEDIUM"
    else:
        risk_label = "🔴 HIGH"

    # ── 5-KPI Row (≤100px) ──────────────────────────────────────
    drill_filter = render_clickable_kpi_row([
        {"label": "Jobs", "value": total_jobs, "caption": "Repository scope", "filter": "Jobs"},
        {"label": "Status", "value": overall_rag, "caption": "Readiness", "filter": "Status"},
        {"label": "Automation", "value": f"{automation_pct}%", "caption": "Auto-migratable", "filter": "Automation"},
        {"label": "Est. Hours", "value": est_hours, "caption": "Migration effort", "filter": "Hours"},
        {"label": "Risk", "value": risk_label, "caption": f"{cloud_blockers} blockers", "filter": "Risk"},
    ], "kpi_filter", "preflight_kpi")

    render_insights_row([
        {"icon": "🤖", "label": "Auto-Migration Potential", "value": f"{automation_pct}% of jobs can be auto-migrated", "sub": "AI-assisted migration reduces manual effort significantly", "color": "#15803d" if automation_pct >= 70 else "#b45309"},
        {"icon": "⏱️", "label": "Estimated Migration Effort", "value": f"{est_hours}h total across {total_jobs} jobs", "sub": "Includes analysis, remediation, and validation phases", "color": "#2563eb"},
        {"icon": "🚦", "label": "Repository Readiness", "value": f"Overall status: {overall_rag}", "sub": f"{cloud_blockers} cloud blockers detected — see Component Risk Matrix below", "color": "#15803d" if overall_rag == "GREEN" else "#b45309" if overall_rag == "AMBER" else "#be123c"},
    ])



    # ── Business Flow ───────────────────────────────────────────
    render_business_flow()

    st.markdown("---")

    # ── Component Risk Matrix ────────────────────────────────────
    st.subheader("🎯 Component Risk Matrix")
    risk_data = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for comp in custom_analysis["custom_components"]:
        risk_data[comp["risk"]].append(f"Custom: {comp['component']} ({comp['usage_count']} uses)")
    for row in deprecated_rows:
        risk_data[row["risk"]].append(f"Deprecated: {row['component']} → {row['replacement']}")
    for j in all_jobs:
        for r in j.get("enterprise_risk_report", []):
            lvl = r.get("risk", "LOW")
            if lvl in risk_data and r.get("component"):
                risk_data[lvl].append(r["component"])

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**🔴 Critical / 🟠 High**")
        for item in risk_data["CRITICAL"][:8]:
            st.markdown(f"- {item}")
        for item in risk_data["HIGH"][:8]:
            st.markdown(f"- {item}")
        if not risk_data["CRITICAL"] and not risk_data["HIGH"]:
            st.success("No critical/high risk components")
    if drill_filter == "Risk":
        st.caption("Filtered by KPI: **Risk** — showing Critical/High only")
    else:
        with col_b:
            st.markdown("**🟡 Medium / 🟢 Low**")
            for item in risk_data["MEDIUM"][:8]:
                st.markdown(f"- {item}")
            for item in risk_data["LOW"][:8]:
                st.markdown(f"- {item}")

    st.markdown("---")

    # ── KPI / Risk / Readiness Export ────────────────────────────
    with st.expander("📄 Export KPI, Risk & Readiness (PDF)", expanded=False):
        kpi_df = pd.DataFrame([
            {"KPI": "Jobs", "Value": str(total_jobs)},
            {"KPI": "Status", "Value": overall_rag},
            {"KPI": "Automation", "Value": f"{automation_pct}%"},
            {"KPI": "Est. Hours", "Value": str(est_hours)},
            {"KPI": "Risk", "Value": str(risk_label)},
        ])
        styled_dataframe(kpi_df, "preflight_kpi_summary", width="stretch", hide_index=True)

        risk_rows = []
        for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            for item in risk_data[level]:
                risk_rows.append({"Risk Level": level, "Item": item})
        risk_table_df = pd.DataFrame(risk_rows)
        if drill_filter == "Risk":
            risk_table_df = risk_table_df[risk_table_df["Risk Level"].isin(["CRITICAL", "HIGH"])]
        styled_dataframe(risk_table_df, "preflight_risk_table", width="stretch", hide_index=True)

        readiness_df = pd.DataFrame([
            {"Metric": "Status", "Value": readiness_score.get("status") or _score_to_rag(readiness_score.get("overall", 0))}
        ])
        styled_dataframe(readiness_df, "preflight_readiness_metrics", width="stretch", hide_index=True)

        pdf_download_button(
            "Preflight KPI & Risk Summary",
            [
                ("KPI Summary", kpi_df),
                ("Risk Table", risk_table_df),
                ("Readiness Metrics", readiness_df),
            ],
            "preflight_kpi_risk_readiness",
            "Preflight_KPI_Risk_Readiness.pdf",
        )

    st.markdown("---")

    # ── Effort Summary ──────────────────────────────────────────
    st.subheader("⏱️ Migration Effort Estimate")
    if effort_estimate:
        e1, e2, e3, e4, e5 = st.columns(5)
        e1.metric("Total Jobs", effort_estimate["total_jobs"])
        e2.metric("Auto-Migratable", f"{effort_estimate['auto_pct']}%")
        e3.metric("Manual Required", f"{effort_estimate['manual_pct']}%")
        e4.metric("Est. Days", effort_estimate["estimated_days"])
        e5.metric("Est. Weeks", effort_estimate["estimated_weeks"])

        by_c = effort_estimate["by_complexity"]
        if sum(by_c.values()) > 0:
            fig = px.pie(
                names=list(by_c.keys()),
                values=list(by_c.values()),
                color=list(by_c.keys()),
                color_discrete_map={
                    "LOW": "#38a169", "MEDIUM": "#d69e2e",
                    "HIGH": "#dd6b20", "CRITICAL": "#e53e3e"
                },
                title="Jobs by Complexity"
            )
            fig.update_layout(height=220, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------
# 2. Custom Component Analyzer
# ---------------------------------------------------------------

def render_custom_component_analyzer(custom_analysis):
    st.header("🔧 Custom Component Analyzer")
    data = custom_analysis.get("custom_components", [])
    if not data:
        st.success("✅ No custom/unknown components detected. All components are in Talend 8 catalog.")
        return

    st.info(
        f"**{custom_analysis['total_custom']}** custom/unknown components found "
        f"across **{custom_analysis['impacted_jobs']}** jobs."
    )
    ai_recommendation = custom_analysis.get("ai_recommendation")
    if ai_recommendation:
        st.subheader("AI Component Migration Recommendation")
        st.markdown(ai_recommendation)

    rows = []
    for item in data:
        rows.append({
            "Component": item["component"],
            "Usage Count": item["usage_count"],
            "Jobs Impacted": len(item["jobs_impacted"]),
            "Risk": item["risk"],
            "Recommendation": item["recommendation"]
        })
    df = pd.DataFrame(rows)
    styled_dataframe(df, "custom_component_analyzer", width="stretch")

    st.subheader("🔍 Drill-Down by Component")
    for item in data:
        risk_col = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(item["risk"], "⚪")
        with st.expander(f"{risk_col} {item['component']} — {item['usage_count']} uses"):
            st.markdown(f"**Risk Level:** {risk_badge(item['risk'])}", unsafe_allow_html=True)
            st.write(f"**Recommendation:** {item['recommendation']}")
            st.write(f"**Impacted Jobs ({len(item['jobs_impacted'])}):**")
            for j in item["jobs_impacted"]:
                st.markdown(f"  - `{j}`")


# ---------------------------------------------------------------
# 3. Deprecated Component Dashboard
# ---------------------------------------------------------------

def render_deprecated_dashboard(deprecated_rows):
    st.header("📉 Deprecated Component Dashboard")
    if not deprecated_rows:
        st.success("✅ No deprecated components found.")
        return

    rows = []
    for r in deprecated_rows:
        rows.append({
            "Component": r["component"],
            "Count": r["count"],
            "Jobs Impacted": len(r["impacted_jobs"]),
            "Replacement": r["replacement"],
            "Auto-Fix": "✅ Yes" if r["auto_fix"] else "❌ No",
            "Risk": r["risk"]
        })
    df = pd.DataFrame(rows)
    styled_dataframe(df, "deprecated_component_dashboard", width="stretch")

    fig = px.bar(
        df, x="Component", y="Count", color="Risk",
        color_discrete_map={"LOW": "#38a169", "MEDIUM": "#d69e2e",
                             "HIGH": "#dd6b20", "CRITICAL": "#e53e3e"},
        title="Deprecated Component Usage"
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("🔍 Drill-Down")
    for r in deprecated_rows:
        af = "✅ Auto-Fix Available" if r["auto_fix"] else "❌ Manual Fix Required"
        with st.expander(f"{r['component']} → {r['replacement']} | {af}"):
            st.markdown(f"**Risk:** {risk_badge(r['risk'])}", unsafe_allow_html=True)
            st.write(f"**Total Occurrences:** {r['count']}")
            st.write(f"**Impacted Jobs ({len(r['impacted_jobs'])}):**")
            for j in r["impacted_jobs"]:
                st.markdown(f"  - `{j}`")


# ---------------------------------------------------------------
# 4. Migration Readiness Status
# ---------------------------------------------------------------

def render_readiness_score(readiness_score):
    st.header("🎯 Migration Readiness Status")
    status = readiness_score.get("status") or _score_to_rag(readiness_score.get("overall", 0))

    st.metric("Migration Readiness", status)

    st.subheader("Status Breakdown")
    breakdown = readiness_score.get("breakdown", [])
    if breakdown:
        for dim in breakdown:
            dim_status = dim.get("status") or dim.get("rag") or _score_to_rag(dim.get("score", 0))
            color = {"GREEN": "🟢", "AMBER": "🟡", "RED": "🔴"}.get(dim_status, "⚪")
            st.markdown(f"{color} **{dim['dimension']}**: {dim_status}")
            st.caption(dim["detail"])


# ---------------------------------------------------------------
# 5. Repository Risk Heatmap
# ---------------------------------------------------------------

def render_readiness_score(readiness_score):
    st.header("Migration Readiness")
    status = readiness_score.get("status") or _score_to_rag(readiness_score.get("overall", 0))

    palette = {
        "GREEN": {"bg": "#f3faf7", "border": "#b8dec9", "text": "#356b4d"},
        "AMBER": {"bg": "#fff9ed", "border": "#ead8a8", "text": "#7a5d24"},
        "RED": {"bg": "#fff5f5", "border": "#e8c4c4", "text": "#8a4a4a"},
    }
    fallback = {"bg": "#f8fafc", "border": "#dbe3ea", "text": "#475569"}
    status_style = palette.get(status, fallback)

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:4px 0 12px;">
            <span style="font-size:12px;font-weight:700;color:#475569;">Migration Readiness</span>
            <span style="display:inline-flex;align-items:center;background:{status_style['bg']};
                         border:1px solid {status_style['border']};color:{status_style['text']};
                         border-radius:999px;padding:5px 11px;font-size:11px;
                         font-weight:800;line-height:1;">{html_lib.escape(str(status))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Breakdown")
    for dim in readiness_score.get("breakdown", []):
        dim_status = dim.get("status") or dim.get("rag") or _score_to_rag(dim.get("score", 0))
        dim_style = palette.get(dim_status, fallback)
        detail = dim.get("detail", "")
        st.markdown(
            f"""
            <div style="background:#ffffff;border:1px solid #e7edf3;border-radius:8px;
                        padding:10px 12px;margin:6px 0;">
                <div style="display:flex;align-items:center;justify-content:space-between;
                            gap:12px;flex-wrap:wrap;">
                    <div style="font-weight:700;color:#334155;">{dim['dimension']}</div>
                    <span style="background:{dim_style['bg']};border:1px solid {dim_style['border']};
                                 color:{dim_style['text']};border-radius:999px;padding:3px 10px;
                                 font-size:11px;font-weight:700;">{dim_status}</span>
                </div>
                <div style="font-size:12px;color:#64748b;margin-top:6px;">{detail}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

def render_risk_heatmap(all_jobs):
    st.header("🔥 Repository Risk Heatmap")
    READINESS_RISK_WEIGHT = {"HIGH": 0, "MEDIUM": 50, "LOW": 100}
    rows = []
    for job in all_jobs:
        jname = job["job_data"]["job_name"]
        comp_count = len(job["job_data"]["components"])
        cloud_readiness = job["cloud_readiness"]
        readiness_level = cloud_readiness.get("readiness", "LOW")
        cloud_status = cloud_readiness.get("rag", "—")
        est = job.get("estimation", {})
        complexity = est.get("complexity", "LOW")
        child_jobs = est.get("child_job_count", 0)
        risk_num = (
            READINESS_RISK_WEIGHT.get(readiness_level, 50) * 0.4 +
            {"LOW": 0, "MEDIUM": 25, "HIGH": 60, "CRITICAL": 100}.get(complexity, 0) * 0.4 +
            min(child_jobs * 10, 100) * 0.2
        )
        if risk_num >= 70:
            risk_level = "🔴 High"
        elif risk_num >= 40:
            risk_level = "🟡 Medium"
        else:
            risk_level = "🟢 Low"
        rows.append({
            "Job Name": jname,
            "Risk Status": risk_level,
            "Risk Level": risk_level,
            "Complexity": complexity,
            "Components": comp_count,
            "Child Deps": child_jobs,
            "Cloud Status": cloud_status
        })

    df = pd.DataFrame(rows)
    styled_dataframe(df, "risk_heatmap", width="stretch", height=400)
    pdf_download_button("Repository Risk Heatmap", [("Risk Heatmap", df)], "risk_heatmap", "Repository_Risk_Heatmap.pdf")

    fig = px.scatter(
        df, x="Components", y="Child Deps", size="Child Deps",
        color="Risk Level", hover_name="Job Name", hover_data=["Cloud Status"],
        color_discrete_map={"🔴 High": "#e53e3e", "🟡 Medium": "#d69e2e", "🟢 Low": "#38a169"},
        title="Risk Scatter: Component Complexity vs Cloud Status"
    )
    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------
# 6. Auto-Fix Recommendation Engine
# ---------------------------------------------------------------

def render_auto_fix_recommendations(recommendations):
    st.header("🔨 Auto-Fix Recommendation Engine")
    if not recommendations:
        st.success("✅ No fix recommendations needed.")
        return

    auto_fixable = [r for r in recommendations if r["auto_fix"]]
    manual = [r for r in recommendations if not r["auto_fix"]]
    st.info(
        f"**{len(recommendations)}** recommendations total | "
        f"**{len(auto_fixable)}** auto-fixable | "
        f"**{len(manual)}** require manual effort"
    )

    tab1, tab2, tab3 = st.tabs(["All Recommendations", "Auto-Fixable", "Manual Required"])

    _EFFORT_COLOR = {
        "high": "🔴 High Effort",
        "medium": "🟡 Medium Effort",
        "low": "🟢 Low Effort",
    }

    def _render_recs(recs, table_key):
        rows = []
        for r in recs:
            rows.append({
                "Job": r["job_name"],
                "Issue": r["issue"],
                "Fix": r["fix"],
                "Risk": r["risk"],
                "Effort": _EFFORT_COLOR.get(str(r["effort"]).lower(), r["effort"]),
                "Auto-Fix": "✅" if r["auto_fix"] else "❌"
            })
        if rows:
            styled_dataframe(pd.DataFrame(rows), table_key, width="stretch")
        else:
            st.success("None in this category.")

    with tab1:
        _render_recs(recommendations, "preflight_rows_all")
    with tab2:
        _render_recs(auto_fixable, "preflight_rows_auto")
    with tab3:
        _render_recs(manual, "preflight_rows_manual")

    effort_counts = pd.Series(
        [str(r["effort"]).capitalize() for r in recommendations]
    ).value_counts().reindex(["High", "Medium", "Low"]).dropna().reset_index()
    effort_counts.columns = ["Effort", "Count"]
    if not effort_counts.empty:
        fig = px.bar(
            effort_counts, x="Effort", y="Count", color="Effort",
            color_discrete_map={"High": "#e53e3e", "Medium": "#d69e2e", "Low": "#38a169"},
            title="Recommendations by Effort"
        )
        st.session_state["_autofix_chart_counter"] = st.session_state.get("_autofix_chart_counter", 0) + 1
        st.plotly_chart(fig, width="stretch", key=f"autofix_effort_chart_{st.session_state['_autofix_chart_counter']}")


# ---------------------------------------------------------------
# 7. Cloud Readiness Analyzer (enhanced)
# ---------------------------------------------------------------

def render_cloud_readiness_analyzer(all_jobs):
    st.header("☁️ Cloud Readiness Analyzer")
    cloud_blockers = {
        "tSystem": [],
        "tLibraryLoad": [],
        "tJava": [],
        "tJavaFlex": [],
        "tBeanShell": [],
    }
    for job in all_jobs:
        jname = job["job_data"]["job_name"]
        for comp in job["job_data"]["components"]:
            ct = comp["component_type"]
            if ct in cloud_blockers:
                cloud_blockers[ct].append(jname)

    c1, c2, c3 = st.columns(3)
    _high_count = sum(1 for j in all_jobs if j["cloud_readiness"]["readiness"] == "HIGH")
    _med_count = sum(1 for j in all_jobs if j["cloud_readiness"]["readiness"] == "MEDIUM")
    _low_count = sum(1 for j in all_jobs if j["cloud_readiness"]["readiness"] == "LOW")
    _total = max(len(all_jobs), 1)
    with c1:
        render_progress_metric("High Readiness Jobs", str(_high_count), round(_high_count/_total*100), f"{round(_high_count/_total*100)}% of portfolio", "#15803d")
    with c2:
        render_progress_metric("Medium Readiness", str(_med_count), round(_med_count/_total*100), f"Remediation needed", "#b45309")
    with c3:
        render_progress_metric("Low Readiness (Blockers)", str(_low_count), round(_low_count/_total*100), f"Cloud blockers present", "#be123c")

    st.subheader("Cloud Blockers Detected")
    blocker_rows = []
    for comp, jobs in cloud_blockers.items():
        if jobs:
            blocker_rows.append({
                "Blocker": comp,
                "Jobs Impacted": len(jobs),
                "Severity": "CRITICAL" if comp == "tSystem" else "HIGH",
                "Recommendation": {
                    "tSystem": "Replace with cloud function/API",
                    "tLibraryLoad": "Validate runtime library availability",
                    "tJava": "Review and refactor custom Java",
                    "tJavaFlex": "Replace with tJavaRow",
                    "tBeanShell": "Replace with tJavaRow"
                }.get(comp, "Manual review required")
            })

    if blocker_rows:
        styled_dataframe(pd.DataFrame(blocker_rows), "cloud_blockers", width="stretch")
    else:
        st.success("✅ No critical cloud blockers detected!")

    rows = [{
        "Job": j["job_data"]["job_name"],
        "Readiness": j["cloud_readiness"]["readiness"]
    } for j in all_jobs]
    df = pd.DataFrame(rows)
    counts = df["Readiness"].value_counts().reset_index()
    counts.columns = ["Readiness", "Jobs"]
    fig = px.bar(
        counts, x="Readiness", y="Jobs", color="Readiness",
        color_discrete_map={"HIGH": "#38a169", "MEDIUM": "#d69e2e", "LOW": "#e53e3e"},
        title="Cloud Readiness per Job"
    )
    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------
# 8. Dependency Visualizer (NetworkX + HTML)
# ---------------------------------------------------------------

def render_dependency_visualizer(all_jobs):
    st.header("🕸️ Job Dependency Visualizer")
    try:
        import networkx as nx
    except ImportError:
        st.warning("Install `networkx` for dependency graph: `pip install networkx`")
        return

    G = nx.DiGraph()
    for job in all_jobs:
        jname = job["job_data"]["job_name"]
        G.add_node(jname)
        deps = job.get("dependencies", {})
        for child in deps.get("child_jobs", []):
            G.add_node(child)
            G.add_edge(jname, child)

    if G.number_of_edges() == 0:
        st.info("No parent-child job dependencies detected in this repository.")
        st.write(f"**{G.number_of_nodes()} independent jobs found:**")
        st.write([n for n in G.nodes()])
        return

    st.info(
        f"Graph: **{G.number_of_nodes()} jobs** | "
        f"**{G.number_of_edges()} dependency edges**"
    )

    roots = [n for n in G.nodes() if G.in_degree(n) == 0]
    leaves = [n for n in G.nodes() if G.out_degree(n) == 0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Parent Jobs (roots)", len(roots))
    c2.metric("Child Jobs (leaves)", len(leaves))
    c3.metric("Dependency Edges", G.number_of_edges())

    st.subheader("Dependency Table")
    dep_rows = []
    for parent, child in G.edges():
        dep_rows.append({"Parent Job": parent, "Child Job": child})
    styled_dataframe(pd.DataFrame(dep_rows), "dependency_table", width="stretch")

    job_meta = {}
    for job in all_jobs:
        jname = job["job_data"]["job_name"]
        complexity = job.get("complexity", {}).get("level", "—")
        risks = [r.get("risk", "") for r in job.get("enterprise_risk_report", [])]
        if "CRITICAL" in risks or "HIGH" in risks:
            risk = "HIGH"
        elif "MEDIUM" in risks:
            risk = "MEDIUM"
        elif risks:
            risk = "LOW"
        else:
            risk = "—"
        job_meta[jname] = {"complexity": complexity, "risk": risk}

    import json as _json
    node_list = []
    for n in G.nodes():
        if n in roots:
            color = "#e53e3e"
            group = "parent"
        elif n in leaves:
            color = "#38a169"
            group = "child"
        else:
            color = "#d69e2e"
            group = "intermediate"
        meta = job_meta.get(n, {"complexity": "—", "risk": "—"})
        node_list.append({"id": n, "label": n, "color": color, "group": group,
                           "risk": meta["risk"], "complexity": meta["complexity"]})

    edge_list = [{"source": u, "target": v} for u, v in G.edges()]
    nodes_json = _json.dumps(node_list)
    edges_json = _json.dumps(edge_list)

    graph_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{ margin: 0; background: #0f1117; font-family: sans-serif; }}
  svg {{ width: 100%; height: 520px; }}
  .node circle {{ stroke: #fff; stroke-width: 1.5px; cursor: pointer; }}
  .node text {{ fill: #e2e8f0; font-size: 12px; pointer-events: none; text-shadow: 0 1px 3px #000; }}
  .link {{ stroke: #4a5568; stroke-opacity: 0.8; stroke-width: 1.5px; marker-end: url(#arrow); }}
  .tooltip {{ position: absolute; background: #2d3748; color: #e2e8f0; padding: 6px 10px; border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0; transition: opacity 0.2s; border: 1px solid #4a5568; }}
</style>
</head>
<body>
<div class="tooltip" id="tooltip"></div>
<svg id="graph">
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="20" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L0,6 L8,3 z" fill="#718096"/>
    </marker>
  </defs>
  <g id="container"></g>
</svg>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const nodes = {nodes_json};
const edges = {edges_json};
const svg = d3.select("#graph");
const width  = document.body.clientWidth  || 800;
const height = 520;
svg.attr("viewBox", `0 0 ${{width}} ${{height}}`);
const g = d3.select("#container");
const tooltip = document.getElementById("tooltip");
const sim = d3.forceSimulation(nodes)
  .force("link",   d3.forceLink(edges).id(d => d.id).distance(160))
  .force("charge", d3.forceManyBody().strength(-400))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .force("collide", d3.forceCollide(50));
const link = g.append("g").selectAll("line").data(edges).join("line").attr("class", "link");
const node = g.append("g").selectAll("g").data(nodes).join("g").attr("class", "node")
  .call(d3.drag()
    .on("start", (event, d) => {{ if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
    .on("drag",  (event, d) => {{ d.fx = event.x; d.fy = event.y; }})
    .on("end",   (event, d) => {{ if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }})
  );
node.append("circle").attr("r", 18).attr("fill", d => d.color)
  .on("mouseover", (event, d) => {{ tooltip.style.opacity = 1; tooltip.innerHTML = `<b>Job Name:</b> ${{d.id}}<br/><b>Complexity:</b> ${{d.complexity}}<br/><b>Risk:</b> ${{d.risk}}<br/><i>Click to open Job Analysis</i>`; }})
  .on("mousemove", event => {{ tooltip.style.left = (event.pageX + 12) + "px"; tooltip.style.top  = (event.pageY - 20) + "px"; }})
  .on("mouseout", () => {{ tooltip.style.opacity = 0; }})
  .on("click", (event, d) => {{
    const target = window.parent || window;
    const url = new URL(target.location.href);
    url.searchParams.set("open_job", d.id);
    target.location.href = url.toString();
  }});
node.append("text").attr("dy", 32).attr("text-anchor", "middle").text(d => d.label.length > 22 ? d.label.slice(0, 20) + "…" : d.label);
sim.on("tick", () => {{
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y).attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
}});
svg.call(d3.zoom().scaleExtent([0.3, 3]).on("zoom", event => g.attr("transform", event.transform)));
</script>
</body>
</html>
"""
    st.subheader("Interactive Dependency Graph")
    st.markdown(
        '<div style="display:flex;gap:18px;align-items:center;margin-bottom:6px;font-size:13px;">'
        '<span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#38a169;margin-right:6px;"></span>Green = Low</span>'
        '<span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#d69e2e;margin-right:6px;"></span>Amber = Medium</span>'
        '<span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#e53e3e;margin-right:6px;"></span>Red = High</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption("🔴 Parent Jobs  |  🟢 Child/Leaf Jobs  |  🟡 Intermediate  — drag nodes, scroll to zoom, click a node to open Job Analysis")
    st.components.v1.html(graph_html, height=540, scrolling=False)

    st.subheader("Longest Dependency Chains")
    try:
        import networkx as nx
        longest = max(nx.dag_longest_path_length(G), default=0)
        path = nx.dag_longest_path(G)
        st.write(f"Longest chain ({longest} hops): `{' → '.join(path)}`")
    except Exception:
        st.write("Could not compute longest path (graph may have cycles).")


# ---------------------------------------------------------------
# 9. Import Validation Dashboard
# ---------------------------------------------------------------

def render_import_validation_dashboard(all_jobs):
    st.header("✅ Import Validation Dashboard")
    total = len(all_jobs)
    failed = sum(1 for j in all_jobs if j["job_data"]["job_name"] == "INVALID_JOB")
    warnings = sum(1 for j in all_jobs for r in j.get("legacy_risk_report", []))
    imported = total - failed

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Imported Jobs", imported)
    c2.metric("❌ Failed Jobs", failed)
    c3.metric("⚠️ Warnings", warnings)
    c4.metric("Success Rate", f"{round(imported/total*100,1) if total else 0}%")

    if failed == 0:
        st.success("All jobs passed validation. Ready for Talend Studio import.")
    else:
        st.error(f"{failed} jobs failed validation. Review below.")

    if warnings > 0:
        st.subheader("Validation Warnings")
        warn_rows = []
        for job in all_jobs:
            for risk in job.get("legacy_risk_report", []):
                warn_rows.append({
                    "Job": job["job_data"]["job_name"],
                    "Component": risk.get("component", ""),
                    "Issue": risk.get("details", {}).get("issue", ""),
                    "Recommendation": risk.get("details", {}).get("recommendation", "")
                })
        if warn_rows:
            styled_dataframe(pd.DataFrame(warn_rows), "validation_warnings", width="stretch")


def render_enterprise_factory(all_jobs, custom_analysis, deprecated_rows,
                               readiness_score, effort_estimate, auto_fix_recs):
    from app.tiap.inventory.inventory_parser import InventoryParser
    from app.tiap.profiling.component_profiler import ComponentProfiler
    from app.tiap.profiling.context_profiler import ContextProfiler
    from app.tiap.profiling.routine_profiler import RoutineProfiler
    from app.tiap.profiling.joblet_profiler import JobletProfiler
    from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder
    from app.tiap.graph.blast_radius import BlastRadiusEngine
    from app.tiap.graph.mermaid_generator import MermaidGenerator
    from app.tiap.graph.flowchart_generator import FlowchartGenerator
    from app.tiap.lineage.impact_analyzer import ImpactAnalyzer
    from app.analyzers.readiness_scorer import RepositoryScoring

    repo_path = st.session_state.get("last_repo_path")
    inventory = st.session_state.get("tiap_inventory") or InventoryParser().build_inventory(all_jobs, repo_path)
    component_profile = st.session_state.get("tiap_component_profile") or ComponentProfiler().profile(all_jobs)
    context_profile = st.session_state.get("tiap_context_profile") or ContextProfiler().profile(all_jobs)
    routine_profile = st.session_state.get("tiap_routine_profile") or RoutineProfiler().profile(all_jobs, repo_path)
    joblet_profile = st.session_state.get("tiap_joblet_profile") or JobletProfiler().profile(all_jobs)
    dependency_profile = st.session_state.get("tiap_dependency_profile") or DependencyGraphBuilder().analyze(all_jobs)
    scoring = st.session_state.get("tiap_repository_scoring") or RepositoryScoring().score(all_jobs, repo_path)

    section(
        "Readiness & Factory",
        "Deep repository intelligence for enterprise architects, migration leads, and delivery teams.",
    )

    st.markdown("""
    <style>
    div[data-testid="stTabs"]{width:100%;}
    button[data-baseweb="tab"]{
        white-space:nowrap !important;
        min-width:auto !important;
        padding:0.45rem 0.85rem !important;
        font-size:0.90rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    parent_tabs = st.tabs([
        "📊 Overview",
        "⚙️ Technical",
        "⚠️ Risk & Dependencies"
    ])

    with parent_tabs[0]:
        overview_tabs = st.tabs(["Portfolio", "Scoring"])
        with overview_tabs[0]:
            kpis = inventory.get("kpis", {})
            cols = st.columns(6)
            with cols[0]:
                metric_card("Jobs", kpis.get("total_jobs", 0), "Migration scope", "blue")
            with cols[1]:
                metric_card("Components", kpis.get("total_components", 0), "Runtime assets", "teal")
            with cols[2]:
                metric_card("Contexts", kpis.get("total_contexts", 0), "Environment variables", "purple")
            with cols[3]:
                metric_card("Joblets", kpis.get("total_joblets", 0), "Reusable flows", "blue")
            with cols[4]:
                metric_card("Routines", kpis.get("total_routines", 0), "Custom code assets", "amber")
            with cols[5]:
                metric_card("Metadata", kpis.get("total_metadata", 0), "Repository metadata", "green")
            section("Portfolio Inventory", "Job-level repository inventory for migration planning.")
            styled_dataframe(pd.DataFrame(inventory.get("jobs", [])), "portfolio_inventory", width="stretch", hide_index=True)

        with overview_tabs[1]:
            cols = st.columns(5)
            with cols[0]:
                rag_metric_card("Migration Readiness", scoring['migration_readiness_score'])
            with cols[1]:
                rag_metric_card("Cloud Readiness", scoring['cloud_readiness_score'])
            cols[2].metric("Complexity", "GREEN" if scoring['repository_complexity_score'] >= 70 else ("AMBER" if scoring['repository_complexity_score'] >= 40 else "RED"))
            cols[3].metric("Documentation", "GREEN" if scoring['documentation_readiness_score'] >= 70 else ("AMBER" if scoring['documentation_readiness_score'] >= 40 else "RED"))
            cols[4].metric("Testing", "GREEN" if scoring['testing_readiness_score'] >= 70 else ("AMBER" if scoring['testing_readiness_score'] >= 40 else "RED"))
            status_rows = [
                {
                    "Signal": key.replace("_score", "").replace("_", " ").title(),
                    "Status": _score_to_rag(value) if isinstance(value, (int, float)) else value,
                }
                for key, value in scoring.items()
                if isinstance(value, (int, float, str))
            ]
            styled_dataframe(pd.DataFrame(status_rows), "status_rows", width="stretch", hide_index=True)
            with st.expander("Raw scoring evidence"):
                st.json(scoring)

    with parent_tabs[1]:
        technical_tabs = st.tabs(["Components", "Contexts", "Code & Routines", "Reuse & Joblets"])
        with technical_tabs[0]:
            dist = component_profile.get("component_distribution", {})
            cols = st.columns(4)
            cols[0].metric("Standard", dist.get("STANDARD", 0))
            cols[1].metric("Deprecated", dist.get("DEPRECATED", 0))
            cols[2].metric("Custom", dist.get("CUSTOM", 0))
            cols[3].metric("Unknown", dist.get("UNKNOWN", 0))
            styled_dataframe(pd.DataFrame(component_profile.get("component_usage", [])), "component_usage", width="stretch")

            from app.api.routes import call_route
            replacement_recs = call_route("replacement_recommendations", all_jobs)
            st.markdown("**Replacement Recommendations**")
            if replacement_recs:
                styled_dataframe(pd.DataFrame(replacement_recs), "replacement_recommendations", width="stretch", hide_index=True)
            else:
                action_panel("Replacement Recommendations", "No deprecated components requiring replacement were detected.", "Clean", "#22c55e")

            remediation_recs = call_route("remediation_recommendations", all_jobs)
            st.markdown("**Remediation Recommendations**")
            if remediation_recs:
                styled_dataframe(pd.DataFrame(remediation_recs), "remediation_recommendations", width="stretch", hide_index=True)
            else:
                action_panel("Remediation Recommendations", "No unsupported components requiring remediation were detected.", "Clean", "#22c55e")

        with technical_tabs[1]:
            cols = st.columns(4)
            cols[0].metric("Duplicates", len(context_profile.get("duplicate_contexts", [])))
            cols[1].metric("Shared", len(context_profile.get("shared_contexts", [])))
            cols[2].metric("Unused", len(context_profile.get("unused_contexts", [])))
            cols[3].metric("Conflicts", len(context_profile.get("context_conflicts", [])))
            context_rows = [
                ("Duplicate Contexts", context_profile.get("duplicate_contexts", [])),
                ("Shared Contexts", context_profile.get("shared_contexts", [])),
                ("Unused Contexts", context_profile.get("unused_contexts", [])),
                ("Context Conflicts", context_profile.get("context_conflicts", [])),
            ]
            for title, rows in context_rows:
                if rows:
                    st.markdown(f"**{title}**")
                    styled_dataframe(pd.DataFrame(rows), "preflight_rows_hidden", width="stretch", hide_index=True)
            if not any(rows for _, rows in context_rows):
                action_panel("Context Health", "No duplicate, unused, or conflicting contexts were detected.", "Clean", "#22c55e")
            with st.expander("Raw context evidence"):
                st.json(context_profile)

        with technical_tabs[2]:
            rows = routine_profile.get("routine_usage", [])
            cols = st.columns(3)
            cols[0].metric("Java Usage", len(routine_profile.get("java_usage", [])))
            cols[1].metric("Cloud Risks", len(routine_profile.get("cloud_risks", [])))
            cols[2].metric("Routines", len(rows))
            styled_dataframe(pd.DataFrame(rows), "preflight_rows", width="stretch")

        with technical_tabs[3]:
            styled_dataframe(pd.DataFrame(joblet_profile.get("joblet_usage_matrix", [])), "joblet_usage_matrix", width="stretch", hide_index=True)
            dependency_matrix = joblet_profile.get("joblet_dependency_matrix", {})
            dep_rows = [
                {"Joblet": key, "Dependencies": ", ".join(map(str, value)) if isinstance(value, list) else str(value)}
                for key, value in dependency_matrix.items()
            ]
            if dep_rows:
                st.markdown("**Joblet Dependencies**")
                styled_dataframe(pd.DataFrame(dep_rows), "joblet_dependencies", width="stretch", hide_index=True)
            else:
                action_panel("Joblet Dependencies", "No reusable joblet dependency chain was detected.", "No blocker", "#14b8a6")

    with parent_tabs[2]:
        risk_tabs = st.tabs(["Dependencies", "Blast Radius", "Flowcharts"])
        with risk_tabs[0]:
            stats = dependency_profile.get("dependency_statistics", {})
            cols = st.columns(4)
            cols[0].metric("Relationships", stats.get("edges", 0))
            cols[1].metric("Parent Jobs", stats.get("parent_jobs", 0))
            cols[2].metric("Child Jobs", stats.get("child_jobs", 0))
            cols[3].metric("Circular", stats.get("circular_dependencies", 0))
            render_dependency_visualizer(all_jobs)

        with risk_tabs[1]:
            job_names = [j.get("job_data", {}).get("job_name", "Unknown") for j in all_jobs]
            selected = st.selectbox("Job", job_names) if job_names else None
            if selected:
                blast = BlastRadiusEngine().analyze(all_jobs, selected)
                impact = ImpactAnalyzer().analyze(all_jobs, selected)
                cols = st.columns(5)
                cols[0].metric("Jobs", len(blast["impacted_jobs"]))
                cols[1].metric("Contexts", len(blast["impacted_contexts"]))
                cols[2].metric("Joblets", len(blast["impacted_joblets"]))
                cols[3].metric("Routines", len(blast["impacted_routines"]))
                cols[4].metric("Risk", blast["risk"])
                st.subheader("Impact Summary")
                asset_rows = [
                    {"Asset Type": "Jobs", "Impacted": ", ".join(map(str, blast.get("impacted_jobs", []))) or "None"},
                    {"Asset Type": "Contexts", "Impacted": ", ".join(map(str, blast.get("impacted_contexts", []))) or "None"},
                    {"Asset Type": "Joblets", "Impacted": ", ".join(map(str, blast.get("impacted_joblets", []))) or "None"},
                    {"Asset Type": "Routines", "Impacted": ", ".join(map(str, blast.get("impacted_routines", []))) or "None"},
                ]
                styled_dataframe(pd.DataFrame(asset_rows), "blast_radius_assets", width="stretch", hide_index=True)
                with st.expander("Raw impact evidence"):
                    st.json({"impact_tree": impact.get("impact_tree", {}), "blast_radius": blast})

        with risk_tabs[2]:
            mermaid = MermaidGenerator()
            flows = FlowchartGenerator().generate(all_jobs)
            st.subheader("Business Flow")
            render_business_flow()
            st.subheader("Mermaid (Technical)")
            _tech_mermaid_code = mermaid.repository_dependency_diagram(all_jobs)
            _render_mermaid(_tech_mermaid_code, height=420)
            st.subheader("Technical Flow")
            st.text(flows["technical_flow"])
            st.subheader("Parent Child Flow")
            st.text(flows["parent_child_flow"])

    documentation = st.session_state.get("tiap_documentation", {})
    refactoring = st.session_state.get("tiap_refactoring", {})
    assessment = st.session_state.get("tiap_assessment", {})
    testing = st.session_state.get("tiap_testing", {})
    governance = st.session_state.get("tiap_governance", {})
    executive = st.session_state.get("tiap_executive_dashboard", {})

    st.markdown("---")
    section(
        "Enterprise Readiness Modules",
        "Supporting evidence for documentation, refactoring, assessment, testing, governance, and executive reporting.",
    )
    exp_docs = st.expander("Documentation Pack")
    exp_refactor = st.expander("Technical Debt & Refactoring")
    exp_assess = st.expander("Migration Assessment")
    exp_test = st.expander("Testing Readiness")
    exp_gov = st.expander("Governance & Compliance")
    exp_exec = st.expander("Executive Data Model")
    with exp_docs:
        st.write("Generated documentation sections:", sorted(documentation.keys()))
        for name, content in documentation.items():
            st.markdown(f"**{name.title()}**")
            st.code(str(content)[:4000])
    with exp_refactor:
        debt_value = refactoring.get("debt_score", 0)
        st.metric("Technical Debt Status", "RED" if debt_value >= 60 else ("AMBER" if debt_value >= 30 else "GREEN"))
        action_panel(
            "Technical Debt",
            f"{len(refactoring.get('findings', []))} modernization findings available for remediation planning.",
            "Evidence ready" if refactoring else "Pending",
            "#f59e0b",
        )
        with st.expander("Raw refactoring evidence"):
            st.json(refactoring)
    with exp_assess:
        rag_metric_card("Migration Readiness", assessment.get('migration_readiness_percent', 0))
        with st.expander("Raw assessment evidence"):
            st.json(assessment)
    with exp_test:
        st.metric("Testing Readiness", "GREEN" if testing.get("testing_readiness_score", 0) >= 70 else ("AMBER" if testing.get("testing_readiness_score", 0) >= 40 else "RED"))
        action_panel(
            "Validation Pack",
            f"{len(testing.get('test_cases', []))} generated test case entries are available.",
            "Evidence ready" if testing else "Pending",
            "#14b8a6",
        )
        with st.expander("Raw testing evidence"):
            st.json(testing)
    with exp_gov:
        pii = governance.get("pii_detection", {})
        pii_value = pii.get("pii_risk_score", 0)
        st.metric("PII Risk", "RED" if pii_value >= 60 else ("AMBER" if pii_value >= 30 else "GREEN"))
        action_panel(
            "Compliance Review",
            "PII risk status from governance assessment.",
            "Review required" if pii_value else "No elevated PII signal",
            "#ef4444" if pii_value else "#22c55e",
        )
        with st.expander("Raw governance evidence"):
            st.json(governance)
    with exp_exec:
        metrics = executive.get("repository_portfolio_metrics", {}) if executive else {}
        if metrics:
            styled_dataframe(
                pd.DataFrame([{"Metric": key.replace("_", " ").title(), "Value": str(value)} for key, value in metrics.items()]),
                "executive_data_model_metrics",
                width="stretch",
                hide_index=True,
            )
        with st.expander("Raw executive data model"):
            st.json(executive)
