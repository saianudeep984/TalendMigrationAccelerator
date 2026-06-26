"""Impact Intelligence dashboard, executive report, and exports."""
import io
import json
import tempfile
from pathlib import Path
from app.impact_analysis.engine import ImpactLineageIntelligenceEngine
from app.impact_analysis.data_impact_analyzer import DataImpactAnalyzer
from app.performance.cache_manager import get_cache_manager


def build_impact_intelligence(jobs, mappings_by_job=None, repository_metadata=None, migration_intelligence=None, readiness=None):
    cache = get_cache_manager()
    fp = cache.fingerprint("impact_analysis", jobs, mappings_by_job, repository_metadata, migration_intelligence, readiness)
    return cache.cache_analysis(
        "impact_analysis",
        lambda: ImpactLineageIntelligenceEngine().analyze(jobs, mappings_by_job, repository_metadata, migration_intelligence, readiness),
        fp,
    )


def impact_report_markdown(data):
    d, u, c = data["deprecated_components"], data["component_usage"], data["criticality"]
    lines = ["# Impact & Lineage Intelligence Report", "", "## Executive Summary", data["executive_summary"],
             "", "## Component Risk Analysis"]
    lines += [f"- {x['component_id']}: {x['impact']} ({x['impact_score']})" for x in data["component_impact"]["components"][:20]] or ["- None"]
    lines += ["", "## Deprecated Components"]
    lines += [f"- {x['job_name']}: {x['component']} -> {x['replacement']} ({x['risk']})" for x in d["findings"]] or ["- None"]
    lines += ["", "## Component Usage"] + [f"- {x['component']}: {x['count']} uses; risk {x['risk']}" for x in u["by_frequency"]]
    lines += ["", "## Column Lineage", f"- Assets: {len(data['lineage']['nodes'])}", f"- Relationships: {len(data['lineage']['edges'])}",
              "", "## Transformation Intelligence"]
    lines += [f"- {k}: {v}" for k, v in data["transformations"]["counts"].items()]
    lines += ["", "## Critical Assets"] + [f"- {x['asset_id']}: {x['criticality']} ({x['score']})" for x in c["critical_assets"]] or ["- None"]
    return "\n".join(lines)


def export_impact_intelligence(data, format):
    format = format.lower().lstrip(".")
    if format == "json": return json.dumps(data, indent=2, default=str).encode()
    markdown = impact_report_markdown(data)
    if format == "html":
        from app.tiap.documentation.export_utils import markdown_to_html
        return markdown_to_html(markdown, "Impact & Lineage Intelligence").encode()
    if format == "pdf":
        from app.tiap.documentation.export_utils import write_pdf
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "impact.pdf"; write_pdf(str(path), markdown); return path.read_bytes()
    if format in {"xlsx", "excel"}:
        import xlsxwriter
        output = io.BytesIO(); book = xlsxwriter.Workbook(output, {"in_memory": True})
        summary = book.add_worksheet("Summary")
        for row, line in enumerate(markdown.splitlines()): summary.write(row, 0, line)
        usage = book.add_worksheet("Component Usage"); usage.write_row(0, 0, ["Component", "Count", "Jobs", "Risk", "Risk Score"])
        for row, item in enumerate(data["component_usage"]["by_frequency"], 1):
            usage.write_row(row, 0, [item["component"], item["count"], item["job_count"], item["risk"], item["risk_score"]])
        assets = book.add_worksheet("Critical Assets"); assets.write_row(0, 0, ["Asset", "Score", "Criticality"])
        for row, item in enumerate(data["criticality"]["columns"], 1): assets.write_row(row, 0, [item["asset_id"], item["score"], item["criticality"]])
        book.close(); return output.getvalue()
    raise ValueError(f"Unsupported export format: {format}")


def render_impact_intelligence_dashboard(data=None):
    import streamlit as st
    data = data or st.session_state.get("impact_intelligence")
    if data is None:
        jobs = st.session_state.get("last_analysis_jobs", [])
        if not jobs: st.info("Run repository analysis to generate impact intelligence."); return None
        data = build_impact_intelligence(jobs, migration_intelligence=st.session_state.get("migration_intelligence"), readiness=st.session_state.get("readiness_score"))
        st.session_state["impact_intelligence"] = data
    from app.ui.design_system_v2 import std_page_header
    std_page_header("💥", "Impact & Lineage Intelligence", "Blast radius and lineage analysis")
    cols = st.columns(4); cols[0].metric("Components", len(data["component_impact"]["components"]))
    cols[1].metric("Compatibility Findings", data["deprecated_components"]["summary"]["total"])
    cols[2].metric("Lineage Assets", len(data["lineage"]["nodes"])); cols[3].metric("Critical Assets", len(data["criticality"]["critical_assets"]))
    st.write(data["executive_summary"])
    tabs = st.tabs(["Component Risk", "Deprecated", "Usage Heatmap", "Column Lineage", "Transformations", "Data Impact", "Critical Assets"])
    with tabs[0]: st.dataframe(data["component_impact"]["components"])
    with tabs[1]: st.dataframe(data["deprecated_components"]["findings"])
    with tabs[2]: st.dataframe(data["component_usage"]["heatmap"])
    with tabs[3]: st.dataframe(data["lineage"]["edges"])
    with tabs[4]: st.code(data["transformations"]["visualization"], language="mermaid")
    with tabs[5]:
        table = st.text_input("Source table", key="impact_source_table"); column = st.text_input("Column (optional)", key="impact_source_column")
        if table: st.json(DataImpactAnalyzer().analyze(data["lineage"], table, column or None))
    with tabs[6]: st.dataframe(data["criticality"]["columns"])
    formats = (("HTML", "html", "text/html"), ("PDF", "pdf", "application/pdf"), ("JSON", "json", "application/json"), ("Excel", "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    for col, (label, ext, mime) in zip(st.columns(4), formats): col.download_button(label, export_impact_intelligence(data, ext), f"impact_intelligence.{ext}", mime)
    return data


render = render_impact_intelligence_dashboard


