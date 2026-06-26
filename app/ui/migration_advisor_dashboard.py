"""
Migration Advisor Dashboard  (F9.5)

Combines ProjectClassifier (project type/source version), the F9.3
TargetVersionRecommendationEngine (target version + confidence), and the
F9.4 WorkflowSelector (recommended actions) into a single dashboard view.
"""

from typing import Any, Dict, List, Optional

import streamlit as st

from app.parser.project_classifier import ProjectType
from app.analyzers.target_version_recommendation_engine import recommend_target_version
from app.migration_guidance.workflow_selector import select_workflow
from app.ui import design_system as ds


def build_migration_advisor_dashboard(
    project_type,
    source_version: str,
    component_usage: Optional[List[str]] = None,
    enterprise_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Headless data builder for the advisor dashboard (no Streamlit calls)."""
    recommendation = recommend_target_version(
        source_version,
        component_usage=component_usage,
        enterprise_features=enterprise_features,
    )

    ptype_value = project_type.value if isinstance(project_type, ProjectType) else str(project_type)

    if not recommendation["supported"]:
        return {
            "projectType": ptype_value,
            "sourceVersion": source_version,
            "targetVersion": None,
            "confidence": "NONE",
            "rationale": recommendation["rationale"],
            "recommendedActions": [],
        }

    workflow = select_workflow(project_type, source_version, recommendation["recommendedTarget"])

    return {
        "projectType": ptype_value,
        "sourceVersion": source_version,
        "targetVersion": recommendation["recommendedTarget"],
        "confidence": recommendation["confidence"],
        "rationale": recommendation["rationale"],
        "recommendedActions": workflow["steps"],
    }


def render_migration_advisor_dashboard(
    project_type,
    source_version: str,
    component_usage: Optional[List[str]] = None,
    enterprise_features: Optional[Dict[str, Any]] = None,
) -> None:
    data = build_migration_advisor_dashboard(project_type, source_version, component_usage, enterprise_features)

    from app.ui.design_system_v2 import std_page_header
    std_page_header("🧭", "Migration Advisor", "AI-powered migration guidance and recommendations")

    c1, c2, c3 = st.columns(3)
    with c1:
        ds.metric_card("Project Type", data["projectType"], accent="blue")
    with c2:
        ds.metric_card("Source Version", data["sourceVersion"], accent="teal")
    with c3:
        ds.metric_card("Target Version", data["targetVersion"] or "N/A", data["confidence"], accent="green")

    ds.section("Recommended Actions")
    if data["recommendedActions"]:
        ds.roadmap([(step, "") for step in data["recommendedActions"]])
    else:
        st.warning(data["rationale"])
