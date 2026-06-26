"""Architecture & Auto-Fix Intelligence dashboard, report, and exports."""
from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from app.architecture.architecture_assessor import ArchitectureAssessmentEngine
from app.autofix.autofix_generator import AutoFixGenerator
from app.autofix.autofix_validator import AutoFixValidationFramework
from app.autofix.confidence_engine import ConfidenceScoringEngine
from app.performance.cache_manager import get_cache_manager


def build_architecture_autofix_intelligence(jobs, readiness=None, migration_intelligence=None, impact_intelligence=None):
    cache = get_cache_manager()
    fp = cache.fingerprint("architecture_analysis", jobs, readiness, migration_intelligence, impact_intelligence)

    def _build():
        architecture = ArchitectureAssessmentEngine().analyze(jobs, readiness, migration_intelligence, impact_intelligence)
        autofix = AutoFixGenerator().generate(jobs, architecture.get("anti_patterns"))
        validation = AutoFixValidationFramework().validate(autofix)
        confidence = ConfidenceScoringEngine().score(
            jobs, architecture, autofix, impact_intelligence, migration_intelligence or architecture.get("migration_intelligence"), readiness
        )
        result = {"architecture": architecture, "autofix": autofix, "validation": validation, "confidence": confidence}
        result["executive_summary"] = (
            f"Architecture maturity is {architecture['architecture_maturity_score']} "
            f"({architecture['scorecard']['rag']}); technical debt is "
            f"{architecture['technical_debt']['technical_debt_band']} with "
            f"{autofix['summary']['total']} remediation recommendations."
        )
        return result

    return cache.cache_analysis("architecture_analysis", _build, fp)


def architecture_autofix_report_markdown(data):
    a, af, c = data["architecture"], data["autofix"], data["confidence"]
    s = a["scorecard"]
    lines = [
        "# Architecture & Auto-Fix Intelligence Report", "", "## Executive Summary", data["executive_summary"], "",
        "## Architecture Scorecard",
        f"- Architecture Quality Score: {s['architecture_quality_score']}",
        f"- Maintainability Score: {s['maintainability_score']}",
        f"- Scalability Score: {s['scalability_score']}",
        f"- Reusability Score: {s['reusability_score']}",
        f"- Migration Readiness Score: {s['migration_readiness_score']}",
        f"- Technical Debt Score: {s['technical_debt_score']}",
        "", "## Technical Debt",
        f"- Debt Band: {a['technical_debt']['technical_debt_band']}",
        f"- Estimated Hours: {a['technical_debt']['estimated_hours']}",
        "", "## Anti-Patterns",
    ]
    lines += [f"- {f['severity']}: {f['asset']} - {f['type']} - {f['message']}" for f in a["anti_patterns"]["findings"]] or ["- None"]
    lines += ["", "## Best Practices"]
    lines += [f"- {r['status']}: {r['description']} ({r['score']})" for r in a["best_practices"]["standards"]]
    lines += ["", "## Auto-Fix Recommendations"]
    lines += [f"- {r['risk']}: {r['job_name']} - {r['type']} -> {r['after_state']}" for r in af["recommendations"]] or ["- None"]
    lines += ["", "## Confidence Scores"]
    lines += [f"- {k}: {v['score']} ({v['band']})" for k, v in c["scores"].items()]
    lines += ["", "## Validation", f"- Valid: {data['validation']['valid']}", f"- Warnings: {len(data['validation']['warnings'])}", f"- Errors: {len(data['validation']['errors'])}"]
    return "\n".join(lines)


def export_architecture_autofix(data, format):
    format = format.lower().lstrip(".")
    if format == "json":
        return json.dumps(data, indent=2, default=str).encode()
    markdown = architecture_autofix_report_markdown(data)
    if format == "html":
        from app.tiap.documentation.export_utils import markdown_to_html
        return markdown_to_html(markdown, "Architecture & Auto-Fix Intelligence").encode()
    if format == "pdf":
        from app.tiap.documentation.export_utils import write_pdf
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "architecture_autofix.pdf"
            write_pdf(str(path), markdown)
            return path.read_bytes()
    if format in {"xlsx", "excel"}:
        import xlsxwriter
        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {"in_memory": True})
        summary = book.add_worksheet("Scorecard")
        for row, line in enumerate(markdown.splitlines()):
            summary.write(row, 0, line)
        anti = book.add_worksheet("Anti-Patterns")
        anti.write_row(0, 0, ["Type", "Asset", "Severity", "Message", "Risk Points"])
        for row, f in enumerate(data["architecture"]["anti_patterns"]["findings"], 1):
            anti.write_row(row, 0, [f["type"], f["asset"], f["severity"], f["message"], f["risk_points"]])
        fixes = book.add_worksheet("Auto-Fix")
        fixes.write_row(0, 0, ["Job", "Type", "Risk", "Auto-Fixable", "Before", "After"])
        for row, r in enumerate(data["autofix"]["recommendations"], 1):
            fixes.write_row(row, 0, [r["job_name"], r["type"], r["risk"], r["auto_fixable"], str(r["before_state"]), str(r["after_state"])])
        conf = book.add_worksheet("Confidence")
        conf.write_row(0, 0, ["Dimension", "Score", "Band"])
        for row, (k, v) in enumerate(data["confidence"]["scores"].items(), 1):
            conf.write_row(row, 0, [k, v["score"], v["band"]])
        book.close()
        return output.getvalue()
    raise ValueError(f"Unsupported export format: {format}")


def render_architecture_intelligence_dashboard(data=None):
    import streamlit as st
    data = data or st.session_state.get("architecture_autofix_intelligence")
    if data is None:
        jobs = st.session_state.get("last_analysis_jobs", [])
        if not jobs:
            st.info("Run repository analysis to generate Architecture & Auto-Fix Intelligence.")
            return None
        data = build_architecture_autofix_intelligence(
            jobs,
            st.session_state.get("readiness_score", {}),
            st.session_state.get("migration_intelligence"),
            st.session_state.get("impact_intelligence"),
        )
        st.session_state["architecture_autofix_intelligence"] = data
    from app.ui.design_system_v2 import std_page_header, section_header
    std_page_header("🏗️", "Architecture & Auto-Fix Intelligence", "Anti-pattern detection and automated remediation")
    a = data["architecture"]
    cols = st.columns(5)
    cols[0].metric("Architecture", a["scorecard"]["architecture_quality_score"])
    cols[1].metric("Maintainability", a["scorecard"]["maintainability_score"])
    cols[2].metric("Debt", a["technical_debt"]["technical_debt_band"])
    cols[3].metric("Auto-Fix", data["autofix"]["summary"]["total"])
    cols[4].metric("Confidence", data["confidence"]["overall_band"])
    st.write(data["executive_summary"])
    tabs = st.tabs(["Scorecard", "Technical Debt", "Anti-Patterns", "Best Practices", "Auto-Fix", "Confidence"])
    with tabs[0]: st.json(a["scorecard"])
    with tabs[1]: st.dataframe(a["technical_debt"]["remediation_items"])
    with tabs[2]: st.dataframe(a["anti_patterns"]["findings"])
    with tabs[3]: st.dataframe(a["best_practices"]["standards"])
    with tabs[4]: st.dataframe(data["autofix"]["recommendations"]); st.json(data["validation"])
    with tabs[5]: st.json(data["confidence"])
    formats = (("HTML", "html", "text/html"), ("PDF", "pdf", "application/pdf"), ("JSON", "json", "application/json"), ("Excel", "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    for col, (label, ext, mime) in zip(st.columns(4), formats):
        col.download_button(label, export_architecture_autofix(data, ext), f"architecture_autofix.{ext}", mime)
    return data


render = render_architecture_intelligence_dashboard



