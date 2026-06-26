"""
TMA – AI Executive Summary Page
Sections: Business Summary | Technical Summary | Risks | Opportunities | Recommendations
Each section capped at 10 lines.
"""
import streamlit as st
from app.tiap.exec_summary.exec_summary import build_executive_summary


def render_exec_summary_page(job_data: dict):
    from app.ui.design_system_v2 import std_page_header
    std_page_header("🤖", "AI Executive Summary", "AI-generated executive briefing")
    st.caption(f"Job: **{job_data.get('job_name', 'Unknown')}**")

    summary = build_executive_summary(job_data)

    with st.expander("💼 Business Summary", expanded=True):
        st.markdown(summary["business_summary"])

    with st.expander("🛠️ Technical Summary", expanded=False):
        st.markdown(summary["technical_summary"])

    with st.expander("🛑 Risks", expanded=False):
        st.markdown(summary["risks"])

    with st.expander("🚀 Opportunities", expanded=False):
        st.markdown(summary["opportunities"])

    with st.expander("💡 Recommendations", expanded=False):
        st.markdown(summary["recommendations"])
