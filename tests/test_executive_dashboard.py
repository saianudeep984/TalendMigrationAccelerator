"""
Validation tests: ExecutiveDashboard model, page binding, and route/navigation
registration.

Covers:
  - ExecutiveDashboard dataclass: to_dict / from_dict round trip
  - ExecutiveDashboard.from_session_data builds correct KPIs from raw inputs
  - ExecutiveDashboardCard renders headlessly without raising
  - executive_dashboard_page.build_executive_dashboard_model binds session data
  - executive_dashboard_page.render_executive_dashboard_page (empty + populated)
  - "executive_dashboard" route key is registered in the nav registry
  - streamlit_app.py routes "executive_dashboard" to the new page module
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.analyzers.models import ExecutiveDashboard


def _job(name, components=None, cloud_score=80, cloud_rag="GREEN",
         complexity="LOW", est_hours=8, risk_findings=None):
    return {
        "job_data": {
            "job_name": name,
            "components": [{"component_type": c} for c in (components or ["tMap"])],
        },
        "cloud_readiness": {"score": cloud_score, "rag": cloud_rag},
        "estimation": {"complexity": complexity, "estimated_hours": est_hours},
        "enterprise_risk_report": risk_findings or [],
    }


SAMPLE_JOBS = [
    _job("Job_Alpha", ["tMap", "tFTPGet", "tJavaFlex"], cloud_score=70, cloud_rag="AMBER",
         complexity="HIGH", est_hours=40, risk_findings=[{"risk": "HIGH"}]),
    _job("Job_Beta", ["tMap", "tLogRow"], cloud_score=90, cloud_rag="GREEN",
         complexity="LOW", est_hours=8),
]


# ── ExecutiveDashboard model ────────────────────────────────────────────────

class TestExecutiveDashboardModel:

    def test_default_construction(self):
        ed = ExecutiveDashboard()
        assert ed.total_jobs == 0
        assert ed.risk_label == "LOW"

    def test_to_dict_keys(self):
        ed = ExecutiveDashboard()
        d = ed.to_dict()
        for key in (
            "totalJobs", "totalComponents", "cloudReadinessStatus",
            "automationPct", "manualPct", "estimatedHours", "estimatedWeeks",
            "estimatedDays", "highRiskCount", "riskLabel",
            "complexityBreakdown", "totalRoutines", "totalJoblets",
        ):
            assert key in d

    def test_to_dict_from_dict_round_trip(self):
        ed = ExecutiveDashboard(
            total_jobs=5, total_components=12, cloud_readiness_status="GREEN",
            automation_pct=80, manual_pct=20, estimated_hours=64,
            estimated_weeks=2, estimated_days=8, high_risk_count=1,
            risk_label="MEDIUM", complexity_breakdown={"LOW": 3, "HIGH": 2},
            total_routines=4, total_joblets=1,
        )
        rebuilt = ExecutiveDashboard.from_dict(ed.to_dict())
        assert rebuilt == ed

    def test_from_session_data_basic_counts(self):
        ed = ExecutiveDashboard.from_session_data(all_jobs=SAMPLE_JOBS)
        assert ed.total_jobs == 2
        assert ed.total_components == 5

    def test_from_session_data_readiness_status(self):
        ed = ExecutiveDashboard.from_session_data(
            all_jobs=SAMPLE_JOBS, readiness={"overall": "AMBER"}
        )
        assert ed.cloud_readiness_status == "AMBER"

    def test_from_session_data_defaults_to_red_status(self):
        ed = ExecutiveDashboard.from_session_data(all_jobs=SAMPLE_JOBS)
        assert ed.cloud_readiness_status == "RED"

    def test_from_session_data_effort_fields(self):
        ed = ExecutiveDashboard.from_session_data(
            all_jobs=SAMPLE_JOBS,
            effort={
                "auto_pct": 65, "manual_pct": 35, "estimated_hours": 80,
                "estimated_weeks": 2, "estimated_days": 10,
                "by_complexity": {"LOW": 1, "HIGH": 1},
            },
        )
        assert ed.automation_pct == 65
        assert ed.manual_pct == 35
        assert ed.estimated_hours == 80
        assert ed.estimated_weeks == 2
        assert ed.complexity_breakdown == {"LOW": 1, "HIGH": 1}

    def test_from_session_data_high_risk_count_and_label(self):
        ed = ExecutiveDashboard.from_session_data(
            all_jobs=SAMPLE_JOBS, effort={"auto_pct": 70}
        )
        assert ed.high_risk_count == 1
        assert ed.risk_label == "HIGH"

    def test_from_session_data_low_risk_when_no_findings_and_high_automation(self):
        clean_jobs = [_job("J1"), _job("J2")]
        ed = ExecutiveDashboard.from_session_data(
            all_jobs=clean_jobs, effort={"auto_pct": 90}
        )
        assert ed.high_risk_count == 0
        assert ed.risk_label == "LOW"

    def test_from_session_data_medium_risk_when_low_automation(self):
        clean_jobs = [_job("J1"), _job("J2")]
        ed = ExecutiveDashboard.from_session_data(
            all_jobs=clean_jobs, effort={"auto_pct": 30}
        )
        assert ed.risk_label == "MEDIUM"

    def test_from_session_data_routines_and_joblets(self):
        ed = ExecutiveDashboard.from_session_data(
            all_jobs=SAMPLE_JOBS,
            routines={"total_routines": 3},
            joblets={"total_joblets": 2},
        )
        assert ed.total_routines == 3
        assert ed.total_joblets == 2

    def test_from_session_data_empty_jobs(self):
        ed = ExecutiveDashboard.from_session_data(all_jobs=[])
        assert ed.total_jobs == 0
        assert ed.total_components == 0


# ── ExecutiveDashboardCard render (headless) ────────────────────────────────

class TestExecutiveDashboardCard:

    def test_renders_without_raising(self):
        from app.ui.design_system_v2 import ExecutiveDashboardCard
        ed = ExecutiveDashboard.from_session_data(all_jobs=SAMPLE_JOBS, effort={"auto_pct": 70})
        ExecutiveDashboardCard(ed)  # must not raise

    def test_accepts_dict_input(self):
        from app.ui.design_system_v2 import ExecutiveDashboardCard
        ed = ExecutiveDashboard.from_session_data(all_jobs=SAMPLE_JOBS)
        ExecutiveDashboardCard(ed.to_dict())  # must not raise


# ── Page binding ─────────────────────────────────────────────────────────────

class TestExecutiveDashboardPage:

    def _reset_session(self):
        import streamlit as st
        for key in (
            "last_analysis_jobs", "readiness_score", "effort_estimate",
            "routine_analysis", "joblet_analysis", "executive_dashboard_model",
        ):
            st.session_state.pop(key, None)
        return st

    def test_build_model_returns_none_without_analysis(self):
        st = self._reset_session()
        from app.ui.executive_dashboard_page import build_executive_dashboard_model
        assert build_executive_dashboard_model() is None

    def test_build_model_binds_session_data(self):
        st = self._reset_session()
        st.session_state["last_analysis_jobs"] = SAMPLE_JOBS
        st.session_state["readiness_score"] = {"overall": "GREEN"}
        from app.ui.executive_dashboard_page import build_executive_dashboard_model
        model = build_executive_dashboard_model()
        assert isinstance(model, ExecutiveDashboard)
        assert model.total_jobs == 2
        assert model.cloud_readiness_status == "GREEN"

    def test_render_page_empty_state_does_not_raise(self):
        self._reset_session()
        from app.ui.executive_dashboard_page import render_executive_dashboard_page
        render_executive_dashboard_page()  # must not raise

    def test_render_page_populated_binds_model_to_session(self):
        st = self._reset_session()
        st.session_state["last_analysis_jobs"] = SAMPLE_JOBS
        st.session_state["readiness_score"] = {"overall": "AMBER"}
        st.session_state["effort_estimate"] = {
            "auto_pct": 65, "manual_pct": 35, "estimated_hours": 96,
            "estimated_weeks": 3, "estimated_days": 12,
            "by_complexity": {"LOW": 1, "HIGH": 1},
        }
        from app.ui.executive_dashboard_page import render_executive_dashboard_page
        render_executive_dashboard_page()  # must not raise
        bound = st.session_state.get("executive_dashboard_model")
        assert isinstance(bound, ExecutiveDashboard)
        assert bound.total_jobs == 2


# ── Route / navigation registration ─────────────────────────────────────────

class TestRouteAndNavigationRegistration:

    def test_nav_registry_contains_executive_dashboard(self):
        from app.ui.design_system_v2 import _NAV_PAGES
        keys = [k for k, _ in _NAV_PAGES]
        assert "executive_dashboard" in keys

    def test_nav_registry_label(self):
        from app.ui.design_system_v2 import _NAV_PAGES
        mapping = dict(_NAV_PAGES)
        assert mapping["executive_dashboard"] == "Executive Dashboard"

    def test_streamlit_app_routes_to_new_page_module(self):
        app_path = os.path.join(os.path.dirname(__file__), "..", "app", "ui", "streamlit_app.py")
        with open(app_path, encoding="utf-8") as f:
            src = f.read()
        assert 'if _sel == "executive_dashboard":' in src
        assert "from app.ui.executive_dashboard_page import render_executive_dashboard_page" in src

    def test_page_module_exposes_required_entry_points(self):
        from app.ui import executive_dashboard_page as page
        assert hasattr(page, "render_executive_dashboard_page")
        assert hasattr(page, "build_executive_dashboard_model")
