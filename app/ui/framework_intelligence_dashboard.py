from __future__ import annotations

import json
from app.framework_analyzer.framework_best_practice import FrameworkBestPracticeAnalyzer
from app.reports.intelligence_exports import export_markdown_report
from app.performance.cache_manager import get_cache_manager


def build_framework_intelligence(jobs):
    cache = get_cache_manager()
    fp = cache.fingerprint("framework_analysis", jobs)
    return cache.cache_analysis(
        "framework_analysis",
        lambda: FrameworkBestPracticeAnalyzer().analyze(jobs),
        fp,
    )


def export_framework_report(data, fmt="json"):
    fmt = (fmt or "json").lower()
    if fmt == "json":
        return json.dumps(data, indent=2, default=str)
    inventory = data.get("framework_inventory", {}).get("framework_inventory", {})
    inventory_rows = [{"framework": k, **v} for k, v in inventory.items()]
    gap_rows = [{"gap": x} for x in data.get("framework_gaps", {}).get("remediation_recommendations", [])]
    return export_markdown_report(
        data,
        framework_report_markdown(data),
        "Framework Intelligence Report",
        fmt,
        {
            "Maturity": [data.get("framework_maturity", {})],
            "Inventory": inventory_rows,
            "Gaps": gap_rows,
        },
    )


def framework_report_markdown(data):
    maturity = data.get("framework_maturity", {})
    gaps = data.get("framework_gaps", {})
    lines = [
        "# Framework Assessment Report",
        "",
        f"- Framework Maturity Score: {maturity.get('framework_maturity_score')}",
        f"- Best Practice Compliance Score: {data.get('best_practice_compliance_score')}",
        f"- Framework Coverage: {data.get('framework_inventory', {}).get('framework_coverage')}%",
        "",
        "## Framework Maturity Report",
    ]
    for key, value in maturity.items():
        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    lines += ["", "## Framework Gap Analysis"]
    lines += [f"- Missing: {x}" for x in gaps.get("missing_capabilities", [])] or ["- No missing capabilities identified"]
    lines += ["", "## Framework Risks"]
    lines += [f"- {x}" for x in data.get("framework_risks", [])] or ["- No framework risks identified"]
    lines += ["", "## Framework Recommendations"]
    lines += [f"- {x}" for x in data.get("recommendations", [])] or ["- Maintain current framework standards"]
    return "\n".join(lines)


def render_framework_intelligence_dashboard(jobs=None, data=None):
    import streamlit as st
    from app.ui.design_system_v2 import std_page_header, section_header
    std_page_header("🧩", "Framework Intelligence", "Framework inventory, gaps and best practices")
    data = data or st.session_state.get("framework_intelligence")
    if data is None and jobs is not None:
        data = build_framework_intelligence(jobs)
        st.session_state["framework_intelligence"] = data
    if not data:
        st.info("Load a repository first.")
        return
    st.metric("Framework Maturity", data["framework_maturity"]["framework_maturity_score"])
    st.metric("Compliance", data["best_practice_compliance_score"])
    section_header("Inventory"); st.json(data["framework_inventory"])
    section_header("Gaps"); st.dataframe(data["framework_gaps"]["remediation_recommendations"], width="stretch")
    section_header("Risks"); st.json(data.get("framework_risks", []))
    st.download_button("Export JSON", export_framework_report(data, "json"), "framework_intelligence.json")
    st.download_button("Export HTML", export_framework_report(data, "html"), "framework_intelligence.html")
    st.download_button("Export Excel", export_framework_report(data, "xlsx"), "framework_intelligence.xlsx")


render = render_framework_intelligence_dashboard


