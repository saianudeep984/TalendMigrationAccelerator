"""Migration Intelligence dashboard, executive report, and exports."""
import io
import json
import tempfile
from pathlib import Path
from app.migration_intelligence.engine import MigrationIntelligenceEngine
from app.performance.cache_manager import get_cache_manager


def build_migration_intelligence(jobs, readiness=None, lineage_service=None):
    cache = get_cache_manager()
    fp = cache.fingerprint("migration_intelligence", jobs, readiness)
    return cache.cache_analysis(
        "migration_intelligence",
        lambda: MigrationIntelligenceEngine().analyze(jobs, readiness, lineage_service),
        fp,
    )


def executive_report_markdown(data):
    c, e, s = data["complexity"], data["effort"], data["strategy"]
    lines = ["# Migration Intelligence Executive Report", "", "## Executive Summary", data["executive_summary"],
             "", "## Migration Complexity Summary", f"- Score: {c['score']}", f"- Band: {c['complexity']}",
             "", "## Effort Estimation", f"- Hours: {e['estimated_hours']}", f"- Duration: {e['estimated_days']} days",
             f"- Team: {e['recommended_team_size']}", "", "## Migration Strategy", f"- Recommendation: {s['strategy']}",
             f"- Rationale: {s['rationale']}", "", "## Wave Plan"]
    lines += [f"- {w['name']}: {', '.join(w['jobs']) or 'No jobs'}" for w in data["migration_waves"]["waves"]]
    lines += ["", "## Critical Dependencies"]
    lines += [f"- {' -> '.join(p)}" for p in data["critical_paths"]["critical_paths"]] or ["- None"]
    lines += ["", "## Risk Breakdown"]
    lines += [f"- {r['severity']}: {r['job_name']} - {r['risk']} ({r['count']})" for r in data["top_risks"]] or ["- None"]
    return "\n".join(lines)


def export_migration_intelligence(data, format):
    format = format.lower().lstrip(".")
    if format == "json": return json.dumps(data, indent=2, default=str).encode()
    markdown = executive_report_markdown(data)
    if format == "html":
        from app.tiap.documentation.export_utils import markdown_to_html
        return markdown_to_html(markdown, "Migration Intelligence").encode()
    if format == "pdf":
        from app.tiap.documentation.export_utils import write_pdf
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.pdf"; write_pdf(str(path), markdown); return path.read_bytes()
    if format in {"xlsx", "excel"}:
        import xlsxwriter
        output = io.BytesIO(); workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Executive Summary")
        for row, line in enumerate(markdown.splitlines()): sheet.write(row, 0, line)
        sheet = workbook.add_worksheet("Job Effort"); sheet.write_row(0, 0, ["Job", "Complexity", "Hours"])
        for row, item in enumerate(data["effort"]["job_breakdown"], 1):
            sheet.write_row(row, 0, [item["job_name"], item["complexity"], item["estimated_hours"]])
        workbook.close(); return output.getvalue()
    raise ValueError(f"Unsupported export format: {format}")


def render_migration_intelligence_dashboard(data=None):
    import streamlit as st
    data = data or st.session_state.get("migration_intelligence")
    if data is None:
        jobs = st.session_state.get("last_analysis_jobs", [])
        if not jobs: st.info("Run repository analysis to generate migration intelligence."); return None
        data = build_migration_intelligence(jobs, st.session_state.get("readiness_score", {}))
        st.session_state["migration_intelligence"] = data
    from app.ui.design_system_v2 import std_page_header, section_header
    std_page_header("🧠", "Migration Intelligence", "Waves, critical paths and risk analysis")
    cols = st.columns(4); cols[0].metric("Complexity", data["complexity"]["complexity"])
    cols[1].metric("Readiness", data["readiness"].get("score", data["readiness"].get("overall", "N/A")))
    cols[2].metric("Estimated Effort", f"{data['effort']['estimated_hours']}h"); cols[3].metric("Strategy", data["strategy"]["strategy"])
    st.write(data["executive_summary"]); section_header("Migration Waves"); st.dataframe(data["migration_waves"]["waves"])
    section_header("Critical Paths"); st.write(data["critical_paths"]["critical_paths"] or "None")
    section_header("Top Risks"); st.dataframe(data["top_risks"])
    impact = st.session_state.get("impact_intelligence")
    if impact:
        section_header("Impact & Lineage")
        st.write(impact["executive_summary"])
    for col, (label, ext, mime) in zip(st.columns(4), (("HTML", "html", "text/html"), ("PDF", "pdf", "application/pdf"), ("JSON", "json", "application/json"), ("Excel", "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))):
        col.download_button(label, export_migration_intelligence(data, ext), f"migration_intelligence.{ext}", mime)
    return data


render = render_migration_intelligence_dashboard


