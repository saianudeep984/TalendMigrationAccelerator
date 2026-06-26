"""
TMA – Migration Assessment Page
Sections: Cloud Readiness | Unsupported Components | Migration Risks | Effort Estimation | Recommendations
"""
import streamlit as st
import pandas as pd
from app.tiap.migration_assessment.migration_assessment import build_migration_assessment


_RAG_EMOJI = {"RED": "🔴", "AMBER": "🟠", "GREEN": "🟢"}
_SEVERITY_EMOJI = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}


def _severity_badge(s: str) -> str:
    return f"{_SEVERITY_EMOJI.get(s, '⚪')} {s}"


def render_migration_assessment_page(job_data: dict):
    st.header("🚀 Migration Assessment")
    st.caption(f"Job: **{job_data.get('job_name', 'Unknown')}**")

    assess = build_migration_assessment(job_data)

    # ── Cloud Readiness ───────────────────────────────────────────────────────
    cloud = assess["cloud_readiness"]
    with st.expander(f"☁️ Cloud Readiness — {_RAG_EMOJI.get(cloud['rag'], '⚪')} {cloud['readiness']}", expanded=True):
        c1, c2 = st.columns(2)
        c1.metric("Readiness", cloud["readiness"])
        c2.metric("RAG Status", cloud["rag"])
        if cloud["java_task_findings"]:
            st.markdown("**Java Task Findings:**")
            st.dataframe(pd.DataFrame(cloud["java_task_findings"]), use_container_width=True, hide_index=True)
        else:
            st.success("No Java task risk findings detected.")

    # ── Unsupported Components ────────────────────────────────────────────────
    unsupported = assess["unsupported_components"]
    with st.expander(f"⚠️ Unsupported Components ({len(unsupported)})", expanded=False):
        if not unsupported:
            st.success("No unsupported components detected.")
        for u in unsupported:
            with st.expander(f"{_severity_badge(u['impact_level'])}  {u['category']} — {u['count']} instance(s)", expanded=False):
                st.markdown(f"**Impact Level:** {u['impact_level']}")
                st.markdown(f"**Jobs Impacted:** {', '.join(u['jobs_impacted'])}")

    # ── Migration Risks ────────────────────────────────────────────────────────
    risks = assess["migration_risks"]
    with st.expander(f"🛑 Migration Risks ({len(risks)})", expanded=False):
        for bucket in ("High", "Medium", "Low"):
            bucket_risks = [r for r in risks if r["bucket"] == bucket]
            if not bucket_risks:
                continue
            st.markdown(f"**{bucket} Risk**")
            for r in bucket_risks:
                with st.expander(f"{_severity_badge(r['risk'])}  {r['component']}", expanded=False):
                    st.markdown(f"**Reason:** {r['reason']}")
                    st.info(f"💡 Recommendation: {r['recommendation']}")
        if not risks:
            st.success("No migration risks identified.")

    # ── Effort Estimation ──────────────────────────────────────────────────────
    effort = assess["effort_estimation"]
    with st.expander("⏱️ Effort Estimation", expanded=False):
        c1, c2 = st.columns(2)
        c1.metric("Estimated Hours", effort["estimated_hours"])
        c2.metric("Complexity", effort["complexity"])
        st.markdown("**Effort Drivers:**")
        for d in effort["effort_drivers"]:
            st.markdown(f"- {d}")

    # ── Recommendations ────────────────────────────────────────────────────────
    with st.expander(f"💡 Recommendations ({len(assess['recommendations'])})", expanded=False):
        for rec in assess["recommendations"]:
            st.markdown(f"- {rec}")

    # ── Summary Table ─────────────────────────────────────────────────────────
    with st.expander("📈 Summary", expanded=False):
        st.dataframe(pd.DataFrame([
            {"Category": "Cloud Readiness",         "Value": f"{cloud['readiness']} ({cloud['rag']})"},
            {"Category": "Unsupported Components",  "Value": len(unsupported)},
            {"Category": "Migration Risks",         "Value": len(risks)},
            {"Category": "Estimated Hours",         "Value": effort["estimated_hours"]},
            {"Category": "Recommendations",         "Value": len(assess["recommendations"])},
        ]), use_container_width=True, hide_index=True)
