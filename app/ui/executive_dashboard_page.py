"""
Executive Dashboard page.

Binds session-state repository analysis data to the ExecutiveDashboard model
(app.analyzers.models.ExecutiveDashboard) and renders it via
ExecutiveDashboardCard, followed by the full detail view (charts, drilldowns,
report pack) provided by app.ui.dashboard.render_executive_dashboard.

Registered route key: "executive_dashboard"
Registered nav entry:  ("executive_dashboard", "Executive Dashboard") in
                        app.ui.design_system_v2._NAV_PAGES
"""
import streamlit as st

from app.analyzers.models import ExecutiveDashboard
from app.ui.design_system_v2 import empty_state_card


def build_executive_dashboard_model() -> ExecutiveDashboard | None:
    """Build the ExecutiveDashboard model from current session-state
    repository analysis data. Returns None if no analysis has been run yet.
    """
    all_jobs = st.session_state.get("last_analysis_jobs")
    if not all_jobs:
        return None
    return ExecutiveDashboard.from_session_data(
        all_jobs=all_jobs,
        readiness=st.session_state.get("readiness_score", {}),
        effort=st.session_state.get("effort_estimate", {}),
        routines=st.session_state.get("routine_analysis", {}),
        joblets=st.session_state.get("joblet_analysis", {}),
    )


def render_executive_dashboard_page() -> None:
    """Entry point for the Executive Dashboard page route."""
    model = build_executive_dashboard_model()
    if model is None:
        empty_state_card(
            "No repository loaded",
            "Upload your Talend ZIP on the Home page first.",
            "warning",
        )
        return

    # Persist the bound model in session state for downstream consumers
    # (report pack, exports, drilldown tables).
    st.session_state["executive_dashboard_model"] = model
    from app.ui.migration_intelligence_dashboard import build_migration_intelligence
    st.session_state["migration_intelligence"] = build_migration_intelligence(
        st.session_state.get("last_analysis_jobs", []),
        st.session_state.get("readiness_score", {}),
    )

    from app.ui.impact_intelligence_dashboard import build_impact_intelligence
    st.session_state["impact_intelligence"] = build_impact_intelligence(
        st.session_state.get("last_analysis_jobs", []),
        migration_intelligence=st.session_state["migration_intelligence"],
        readiness=st.session_state.get("readiness_score", {}),
    )
    from app.ui.upgrade_advisor_dashboard import build_upgrade_advisor
    from app.ui.migration_runbook_dashboard import build_migration_runbook
    from app.ui.framework_intelligence_dashboard import build_framework_intelligence
    _exec_jobs = st.session_state.get("last_analysis_jobs", [])
    if _exec_jobs:
        st.session_state["upgrade_advisor"] = build_upgrade_advisor(_exec_jobs)
        st.session_state["migration_runbook"] = build_migration_runbook(_exec_jobs, st.session_state.get("upgrade_advisor"))
        st.session_state["framework_intelligence"] = build_framework_intelligence(_exec_jobs)

    from app.ui.architecture_intelligence_dashboard import build_architecture_autofix_intelligence
    st.session_state["architecture_autofix_intelligence"] = build_architecture_autofix_intelligence(
        st.session_state.get("last_analysis_jobs", []),
        readiness=st.session_state.get("readiness_score", {}),
        migration_intelligence=st.session_state.get("migration_intelligence"),
        impact_intelligence=st.session_state.get("impact_intelligence"),
    )
    from app.ui.dashboard import render_executive_dashboard
    render_executive_dashboard()

