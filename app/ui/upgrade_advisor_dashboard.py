from __future__ import annotations

import json
from typing import Any, Mapping

from app.reports.intelligence_exports import export_markdown_report
from app.upgrade_advisor.recommendation_engine import UpgradeRecommendationEngine
from app.performance.cache_manager import get_cache_manager


def build_upgrade_advisor(jobs, source_version="Talend 7.x", target_version="Talend 8.x"):
    cache = get_cache_manager()
    fp = cache.fingerprint("upgrade_advisor", jobs, source_version, target_version)
    return cache.cache_analysis(
        "upgrade_advisor",
        lambda: UpgradeRecommendationEngine().recommend(jobs, source_version, target_version),
        fp,
    )


def export_upgrade_report(data: Mapping[str, Any], fmt="json"):
    fmt = (fmt or "json").lower()
    if fmt == "json":
        return json.dumps(data, indent=2, default=str)
    return export_markdown_report(
        data,
        upgrade_report_markdown(data),
        "Upgrade Advisor Report",
        fmt,
        {
            "Compatibility": data.get("compatibility", {}).get("findings", []),
            "Breaking": data.get("breaking_changes", {}).get("findings", []),
            "Deprecated": data.get("deprecated_components", {}).get("findings", []),
            "Manual Fixes": data.get("manual_remediation", {}).get("manual_fix_inventory", []),
        },
    )


def upgrade_report_markdown(data):
    inv = data.get("inventory", {})
    impact = data.get("impact_assessment", {})
    ready = data.get("readiness", {})
    effort = data.get("effort_estimate", {})
    rec = data.get("recommendation", {})
    lines = [
        "# Executive Upgrade Summary",
        "",
        f"- Source Version: {inv.get('source_version')}",
        f"- Target Version: {inv.get('target_version')}",
        f"- Upgrade Recommendation: {rec.get('decision')}",
        f"- Readiness Score: {ready.get('upgrade_readiness_percent')}%",
        f"- Impact: {impact.get('classification')} ({impact.get('upgrade_impact_score')})",
        f"- Estimated Effort: {effort.get('total_hours')} hours",
        "",
        "## Technical Upgrade Assessment",
        f"- Compatibility Score: {impact.get('compatibility_score')}",
        f"- Upgrade Risk Score: {impact.get('upgrade_risk_score')}",
        f"- Auto-Fix Coverage: {data.get('autofix_opportunity', {}).get('auto_fix_coverage_percent')}%",
        f"- Manual Hours: {data.get('manual_remediation', {}).get('total_manual_hours')}",
        "",
        "## Compatibility Report",
    ]
    for key, value in data.get("compatibility", {}).get("summary", {}).items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## Remediation Plan"]
    manual = data.get("manual_remediation", {}).get("manual_fix_inventory", [])
    lines += [f"- {x.get('asset')}: {x.get('risk_level')} / {x.get('estimated_effort_hours')}h" for x in manual] or ["- No manual remediation identified"]
    lines += ["", "## Upgrade Roadmap"] + [f"- {x}" for x in rec.get("next_actions", [])]
    return "\n".join(lines)


def render_upgrade_advisor_dashboard(jobs=None, data=None):
    import streamlit as st
    from app.ui.design_system_v2 import std_page_header, section_header
    std_page_header("⬆️", "Talend Upgrade Advisor", "Version compatibility and upgrade path analysis")
    data = data or st.session_state.get("upgrade_advisor")
    if data is None and jobs is not None:
        data = build_upgrade_advisor(jobs)
        st.session_state["upgrade_advisor"] = data
    if not data:
        st.info("Load a repository first.")
        return
    cols = st.columns(5)
    cols[0].metric("Source", data["inventory"]["source_version"])
    cols[1].metric("Target", data["inventory"]["target_version"])
    cols[2].metric("Readiness", data["readiness"]["upgrade_readiness_percent"])
    cols[3].metric("Impact", data["impact_assessment"]["classification"])
    cols[4].metric("Decision", data["recommendation"]["decision"])
    section_header("Compatibility Summary"); st.json(data.get("compatibility", {}).get("summary", {}))
    section_header("Breaking Changes"); st.dataframe(data["breaking_changes"]["findings"], width="stretch")
    section_header("Deprecated Components"); st.dataframe(data["deprecated_components"]["findings"], width="stretch")
    st.download_button("Export JSON", export_upgrade_report(data, "json"), "upgrade_advisor.json")
    st.download_button("Export HTML", export_upgrade_report(data, "html"), "upgrade_advisor.html")
    st.download_button("Export Excel", export_upgrade_report(data, "xlsx"), "upgrade_advisor.xlsx")


render = render_upgrade_advisor_dashboard


