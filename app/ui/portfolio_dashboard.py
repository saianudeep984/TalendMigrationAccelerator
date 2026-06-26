"""
Portfolio Dashboard — cross-project migration portfolio overview.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from app.ui.design_system_v2 import page_header, render_kpi_row, styled_dataframe, render_insights_row, render_progress_metric


def render_portfolio_dashboard():
    page_header("📊", "Portfolio Dashboard", "Cross-project migration portfolio overview.")

    all_jobs = st.session_state.get("last_analysis_jobs", [])
    total_jobs = len(all_jobs)

    effort = st.session_state.get("effort_estimate", {})
    total_hours = effort.get("estimated_hours", 0) if effort else 0
    auto_pct = effort.get("auto_pct", 0) if effort else 0

    hourly_rate = st.number_input("Hourly Rate", min_value=0.0, value=50.0, step=1.0, key="portfolio_hourly_rate")
    total_cost = total_hours * hourly_rate

    # Color-coded KPI row
    render_kpi_row([
        {"label": "Total Jobs", "value": total_jobs, "caption": "Repository scope", "color": "#1d4ed8"},
        {"label": "Total Hours", "value": total_hours, "caption": "Migration effort", "color": "#7c3aed"},
        {"label": "Automation %", "value": f"{auto_pct}%", "caption": "Auto-migratable", "color": "#15803d" if auto_pct >= 70 else "#b45309"},
        {"label": "Total Cost", "value": f"${total_cost:,.0f}", "caption": f"@ ${hourly_rate:.0f}/hr", "color": "#0f766e"},
    ])

    # Intelligent Insights
    _high_risk_jobs = sum(1 for j in all_jobs if (j.get("complexity", {}).get("complexity", "LOW") in ("HIGH", "CRITICAL")))
    render_insights_row([
        {"icon": "🤖", "label": "Automation Potential", "value": f"{auto_pct}% of jobs can be auto-migrated", "sub": "AI-assisted migration can significantly reduce delivery time", "color": "#15803d" if auto_pct >= 70 else "#b45309"},
        {"icon": "⚠️", "label": "High-Risk Jobs", "value": f"{_high_risk_jobs} of {total_jobs} jobs need manual attention", "sub": "HIGH/CRITICAL complexity — plan extra sprint capacity", "color": "#be123c" if _high_risk_jobs > 0 else "#15803d"},
        {"icon": "💰", "label": "Estimated Investment", "value": f"${total_cost:,.0f} total at current rate", "sub": f"{total_hours}h × ${hourly_rate:.0f}/hr — adjust rate above to recalculate", "color": "#0f766e"},
    ])


    st.markdown("#### Complexity Distribution")
    levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    by_c = effort.get("by_complexity", {}) if effort else {}
    if by_c and sum(by_c.values()) > 0:
        counts = [by_c.get(level, 0) for level in levels]
        _total_cx = sum(counts)
        _cx_colors = {"LOW": "#15803d", "MEDIUM": "#b45309", "HIGH": "#be123c", "CRITICAL": "#7f1d1d"}
        _cx_col1, _cx_col2 = st.columns([2, 1])
        with _cx_col1:
            fig = px.bar(
                x=levels, y=counts, color=levels,
                color_discrete_map={
                    "LOW": "#38a169", "MEDIUM": "#d69e2e",
                    "HIGH": "#e53e3e", "CRITICAL": "#e53e3e",
                },
                labels={"x": "Complexity", "y": "Jobs"},
            )
            fig.update_layout(height=280, margin=dict(t=10, b=0, l=0, r=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        with _cx_col2:
            for _lvl, _cnt in zip(levels, counts):
                _pct = round(_cnt / _total_cx * 100) if _total_cx else 0
                render_progress_metric(_lvl, str(_cnt), _pct, f"{_pct}% of portfolio", _cx_colors.get(_lvl, "#2563eb"))
    else:
        st.caption("Complexity Distribution — run analysis first.")


    st.markdown("#### Risk Distribution")
    risk_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_counts = {level: 0 for level in risk_levels}
    for j in all_jobs:
        for r in j.get("enterprise_risk_report", []):
            level = (r.get("risk") or "").upper()
            if level in risk_counts:
                risk_counts[level] += 1

    if sum(risk_counts.values()) > 0:
        fig2 = px.bar(
            x=risk_levels, y=[risk_counts[level] for level in risk_levels], color=risk_levels,
            color_discrete_map={
                "LOW": "#38a169", "MEDIUM": "#d69e2e",
                "HIGH": "#e53e3e", "CRITICAL": "#e53e3e",
            },
            labels={"x": "Risk", "y": "Findings"},
        )
        fig2.update_layout(height=280, margin=dict(t=10, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig2, width="stretch")
    else:
        st.caption("Risk Distribution — run analysis first.")

    st.markdown("#### Top Risk Jobs")
    _risk_rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
    rows = []
    for j in all_jobs:
        jd = j.get("job_data", {})
        complexity = j.get("complexity", {})
        findings = j.get("enterprise_risk_report", [])
        high_critical = sum(1 for r in findings if (r.get("risk") or "").upper() in ("HIGH", "CRITICAL"))
        rows.append({
            "Job Name": jd.get("job_name", "—"),
            "Complexity": complexity.get("complexity", "—"),
            "Score": complexity.get("score", 0),
            "High/Critical Findings": high_critical,
            "Total Findings": len(findings),
        })
    if rows:
        df = pd.DataFrame(rows)
        df["_rank"] = df["Complexity"].map(_risk_rank).fillna(-1)
        df = df.sort_values(
            by=["_rank", "High/Critical Findings", "Score"],
            ascending=False,
        ).drop(columns="_rank").reset_index(drop=True)
        styled_dataframe(df, "top_risk_jobs", width="stretch", hide_index=True)
    else:
        st.caption("Top Risk Jobs — run analysis first.")

    st.markdown("#### Migration Wave 1")
    st.caption("Jobs with no dependencies on other jobs — safe to migrate first.")
    wave1_rows = []
    for j in all_jobs:
        jd = j.get("job_data", {})
        complexity = j.get("complexity", {})
        child_jobs = j.get("dependencies", {}).get("child_jobs", [])
        if not child_jobs:
            wave1_rows.append({
                "Job Name": jd.get("job_name", "—"),
                "Complexity": complexity.get("complexity", "—"),
                "Score": complexity.get("score", 0),
            })
    wave1_names = set()
    if wave1_rows:
        wave1_df = pd.DataFrame(wave1_rows).sort_values(by="Score").reset_index(drop=True)
        wave1_names = set(wave1_df["Job Name"])
        styled_dataframe(wave1_df, "migration_wave_1", width="stretch", hide_index=True)
    else:
        st.caption("Migration Wave 1 — run analysis first.")

    st.markdown("#### Migration Wave 2")
    st.caption("Jobs whose dependencies are fully covered by Migration Wave 1.")
    wave2_rows = []
    for j in all_jobs:
        jd = j.get("job_data", {})
        complexity = j.get("complexity", {})
        job_name = jd.get("job_name", "—")
        child_jobs = j.get("dependencies", {}).get("child_jobs", [])
        if child_jobs and job_name not in wave1_names and set(child_jobs).issubset(wave1_names):
            wave2_rows.append({
                "Job Name": job_name,
                "Complexity": complexity.get("complexity", "—"),
                "Score": complexity.get("score", 0),
            })
    wave2_names = set()
    if wave2_rows:
        wave2_df = pd.DataFrame(wave2_rows).sort_values(by="Score").reset_index(drop=True)
        wave2_names = set(wave2_df["Job Name"])
        styled_dataframe(wave2_df, "migration_wave_2", width="stretch", hide_index=True)
    else:
        st.caption("Migration Wave 2 — run analysis first.")

    st.markdown("#### Migration Wave 3")
    st.caption("Jobs whose dependencies are fully covered by Migration Waves 1-2.")
    covered_names = wave1_names | wave2_names
    wave3_rows = []
    for j in all_jobs:
        jd = j.get("job_data", {})
        complexity = j.get("complexity", {})
        job_name = jd.get("job_name", "—")
        child_jobs = j.get("dependencies", {}).get("child_jobs", [])
        if (
            child_jobs
            and job_name not in covered_names
            and set(child_jobs).issubset(covered_names)
        ):
            wave3_rows.append({
                "Job Name": job_name,
                "Complexity": complexity.get("complexity", "—"),
                "Score": complexity.get("score", 0),
            })
    if wave3_rows:
        wave3_df = pd.DataFrame(wave3_rows).sort_values(by="Score").reset_index(drop=True)
        styled_dataframe(wave3_df, "migration_wave_3", width="stretch", hide_index=True)
    else:
        st.caption("Migration Wave 3 — run analysis first.")

    st.markdown("No metrics yet.")
