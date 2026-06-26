"""
Job Analysis Page — shows core identity details for a selected job.
"""

import os
import re
import logging
import hashlib
import html as html_lib

try:
    import pandas as pd
except ModuleNotFoundError:
    class _MiniDataFrame(list):
        def __init__(self, data=None, *args, **kwargs):
            super().__init__(data or [])

        @property
        def empty(self):
            return len(self) == 0

        def to_dict(self, *args, **kwargs):
            return list(self)

    class _MiniPandas:
        DataFrame = _MiniDataFrame

    pd = _MiniPandas()

try:
    import streamlit as st
except ModuleNotFoundError:
    class _StreamlitShim:
        session_state = {}

        def cache_data(self, *args, **kwargs):
            return lambda fn: fn

        def __getattr__(self, name):
            if name in {"columns", "tabs"}:
                return lambda *args, **kwargs: [self for _ in range(len(args[0]) if args and isinstance(args[0], (list, tuple)) else 1)]
            return lambda *args, **kwargs: None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    st = _StreamlitShim()

from app.analyzers.auto_fix_engine import generate_auto_fix_recommendations
try:
    from app.ui.column_mapping_page import render_column_mapping_tab
except ModuleNotFoundError as _column_mapping_import_error:
    _COLUMN_MAPPING_IMPORT_ERROR = str(_column_mapping_import_error)

    def render_column_mapping_tab(*args, **kwargs):
        st.warning(f"Column Mapping is unavailable: {_COLUMN_MAPPING_IMPORT_ERROR}")
from app.ui.cached_lineage_page import render_cached_lineage_page
from app.parser.source_target_extractor import build_source_target_inventory, extract_sql_operations
from app.tiap.models.repository import component_parameters, normalize_name
from app.ui.design_system_v2 import (
    page_header,
    pdf_download_button,
    empty_state_card,
    render_mermaid_diagram,
    render_kpi_badge,
    render_kpi_row,
)
try:
    from app.ui.executive_flow_layout import render_executive_job_360
except ModuleNotFoundError as _executive_flow_import_error:
    _EXECUTIVE_FLOW_IMPORT_ERROR = str(_executive_flow_import_error)

    def render_executive_job_360(*args, **kwargs):
        st.warning(f"Executive Flow is unavailable: {_EXECUTIVE_FLOW_IMPORT_ERROR}")
from app.analyzers.complexity_analyzer import EFFORT_HOURS
from app.analyzers.java_logic_analyzer import analyze_java_logic
from app.analyzers.readiness_scorer import score_to_rag as _score_to_rag
try:
    from app.ai.llm_engine import ask_ollama
except ModuleNotFoundError as _ollama_import_error:
    _OLLAMA_IMPORT_ERROR = str(_ollama_import_error)

    def ask_ollama(*args, **kwargs):
        return f"AI explanation unavailable: {_OLLAMA_IMPORT_ERROR}"

logger = logging.getLogger(__name__)

try:
    import networkx as nx
except ModuleNotFoundError:
    class _MiniNetworkXUnfeasible(Exception):
        pass

    class _MiniDiGraph:
        def __init__(self):
            self.nodes = []
            self._node_set = set()
            self._edges = []

        def add_node(self, node):
            if node not in self._node_set:
                self._node_set.add(node)
                self.nodes.append(node)

        def add_edge(self, src, tgt):
            self.add_node(src)
            self.add_node(tgt)
            self._edges.append((src, tgt))

    class _MiniNetworkX:
        DiGraph = _MiniDiGraph
        NetworkXUnfeasible = _MiniNetworkXUnfeasible

        @staticmethod
        def topological_sort(graph):
            indegree = {node: 0 for node in graph.nodes}
            children = {node: [] for node in graph.nodes}
            for src, tgt in graph._edges:
                if src not in indegree:
                    indegree[src] = 0
                    children[src] = []
                if tgt not in indegree:
                    indegree[tgt] = 0
                    children[tgt] = []
                indegree[tgt] += 1
                children[src].append(tgt)

            ready = [node for node in graph.nodes if indegree.get(node, 0) == 0]
            ordered = []
            while ready:
                node = ready.pop(0)
                ordered.append(node)
                for child in children.get(node, []):
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        ready.append(child)
            if len(ordered) != len(indegree):
                raise _MiniNetworkXUnfeasible("cycle detected")
            return ordered

    nx = _MiniNetworkX()

JOB360_CATEGORY_LABELS = [
    "Overview",
    "Executive & Migration",
    "Architecture",
    "Mapping & Lineage",
    "Technical Analysis",
    "Documentation",
    "Export Center",
]

JOB360_SECTION_CATEGORIES = {
    "Dashboard": "Overview",
    "Summary": "Overview",
    "Functional": "Overview",
    "Executive Summary": "Overview",
    "AI Summary": "Overview",
    "Executive Flow": "Executive & Migration",
    "Migration": "Executive & Migration",
    "AI Copilot": "Executive & Migration",
    "Migration Assessment": "Executive & Migration",
    "Validation": "Executive & Migration",
    "Flowcharts": "Architecture",
    "Data Flow": "Architecture",
    "Dependencies": "Architecture",
    "Job Architecture": "Architecture",
    "Source Architecture": "Architecture",
    "Target Architecture": "Architecture",
    "Transformation Architecture": "Architecture",
    "Job Flow Architecture": "Architecture",
    "Column Mapping": "Mapping & Lineage",
    "Source-To-Target Mapping": "Mapping & Lineage",
    "Column Lineage": "Mapping & Lineage",
    "Lineage": "Mapping & Lineage",
    "SQL": "Technical Analysis",
    "Java Logic": "Technical Analysis",
    "Error Handling": "Technical Analysis",
    "Audit": "Technical Analysis",
    "Performance": "Technical Analysis",
    "Security": "Technical Analysis",
    "TDD": "Documentation",
    "Docs Hub": "Documentation",
    "Testing": "Documentation",
    "Export Reports": "Export Center",
}


def _render_tdd_tab_content():
    """Render TDD page content inline inside Job 360 tab."""
    import app.ui.tdd_page as _tdd_mod
    _tdd_mod._KEY_CTX = "_j360"
    from app.ui.tdd_page import (
        _SECTIONS,
        _render_tdd_download_section,
        _render_executive_summary,
        _render_architecture,
        _render_source_architecture,
        _render_target_architecture,
        _render_mapping,
        _render_transformation_architecture,
        _render_job_flow_architecture,
        _render_column_lineage_tdd,
        _render_validation,
        _render_error_handling,
        _render_audit_monitoring,
        _render_performance,
        _render_security,
        _render_dependency_architecture,
        _render_testing_section,
        _render_migration_assessment_section,
        _render_ai_summary_section,
    )
    col_l, col_r = st.columns([6, 2])
    with col_l:
        st.caption("Executive Summary and all analysis sections are auto-populated per selected job.")
    with col_r:
        _tdd_export_popover = st.popover("⬇️  Download TDD", use_container_width=True)
        with _tdd_export_popover:
            _render_tdd_download_section(_key_suffix="_j360")

    st.divider()

    section_labels = [f"{icon} {name}" for icon, name, _ in _SECTIONS]
    selected_label = st.radio(
        "Jump to section", section_labels,
        horizontal=True, label_visibility="collapsed", key="tdd_section_nav_j360",
    )
    selected_idx = section_labels.index(selected_label)

    st.divider()

    icon, name, desc = _SECTIONS[selected_idx]
    label_html = (
        f'<div style="border-left:4px solid #6366f1;padding:6px 0 4px 14px;margin-bottom:10px;">'
        + f'<span style="font-size:20px">{icon}</span> '
        + f'<span style="font-size:17px;font-weight:700;color:#0f172a">{name}</span>'
        + (f'<br><span style="font-size:12px;color:#64748b">{desc}</span>' if desc else '')
        + '</div>'
    )
    st.markdown(label_html, unsafe_allow_html=True)

    _RENDERERS = [
        _render_executive_summary,
        _render_architecture,
        _render_source_architecture,
        _render_target_architecture,
        _render_mapping,
        _render_transformation_architecture,
        _render_job_flow_architecture,
        _render_column_lineage_tdd,
        _render_validation,
        _render_error_handling,
        _render_audit_monitoring,
        _render_performance,
        _render_security,
        _render_dependency_architecture,
        _render_testing_section,
        _render_migration_assessment_section,
        _render_ai_summary_section,
    ]
    _RENDERERS[selected_idx]()


def _render_docs_hub_tab_content():
    """Render Documentation Hub content inline inside Job 360 tab."""
    import app.ui.tdd_page as _tdd_mod
    _tdd_mod._KEY_CTX = "_dh"
    from app.ui.documentation_hub_page import (
        _inject_css,
        _doc_sidebar,
        _build_document_registry,
        _render_kpi_cards,
        _render_tdd_section,
        _render_sticky_toolbar,
    )
    _inject_css()
    section = _doc_sidebar()
    docs = _build_document_registry()
    _render_kpi_cards(docs)
    st.divider()
    if section == "tdd":
        _render_tdd_section()
    _render_sticky_toolbar(section)


def _render_documentation_summary(
    job: dict,
    jd: dict,
    inv: dict,
    all_recs: list[dict],
    sql_ops: list[dict],
    job_name: str,
) -> None:
    """Render business/technical documentation summaries without replacing TDD."""
    components = jd.get("components", [])
    complexity = job.get("complexity", {})
    dependencies = job.get("dependencies", {})
    cloud = job.get("cloud_readiness", {})
    sources = [s.get("name") or s.get("qualified_name") for s in inv.get("sources", []) if s.get("name") or s.get("qualified_name")]
    targets = [t.get("name") or t.get("qualified_name") for t in inv.get("targets", []) if t.get("name") or t.get("qualified_name")]
    java_components = [c for c in components if c.get("component_type") in {"tJava", "tJavaRow", "tJavaFlex"}]
    tmaps = [c for c in components if c.get("component_type") == "tMap"]
    job_recs = [r for r in all_recs if r.get("job_name") == job_name]
    risk_factors = complexity.get("risk_factors", []) or []
    enterprise_risks = job.get("enterprise_risk_report", []) or []
    high_risks = [
        r for r in enterprise_risks
        if str(r.get("risk") or r.get("severity") or "").upper() in {"HIGH", "CRITICAL"}
    ]
    level = complexity.get("complexity") or complexity.get("level") or "LOW"
    score = complexity.get("score", "—")
    readiness = _cloud_rag(cloud)
    effort = EFFORT_HOURS["manual"] if level in ("HIGH", "CRITICAL") else EFFORT_HOURS["auto"]

    st.markdown("#### Documentation Summary")
    render_kpi_row([
        {"label": "Business Summary", "value": len(sources) + len(targets), "caption": "source/target assets", "color": "#1d4ed8"},
        {"label": "Technical Summary", "value": len(components), "caption": "components", "color": "#0f766e"},
        {"label": "Migration Notes", "value": f"{effort}h", "caption": f"{level} complexity", "color": "#b45309"},
        {"label": "Risks", "value": len(high_risks) + len(risk_factors), "caption": "risk items", "color": "#be123c" if high_risks or risk_factors else "#15803d"},
    ])

    doc_tabs = st.tabs(["Business Summary", "Technical Summary", "Migration Notes", "Risks", "Recommendations"])

    with doc_tabs[0]:
        st.markdown("##### Business Summary")
        src_text = ", ".join(sources[:8]) or "no detected source assets"
        tgt_text = ", ".join(targets[:8]) or "no detected target assets"
        st.info(
            f"{job_name} moves or prepares data from {src_text} to {tgt_text}. "
            f"The job contains {len(components)} component(s), including {len(tmaps)} mapping component(s), "
            f"and supports the repository migration assessment by exposing source, target, transformation, and dependency context."
        )
        st.dataframe(
            pd.DataFrame([
                {"Area": "Sources", "Details": src_text},
                {"Area": "Targets", "Details": tgt_text},
                {"Area": "Business Purpose", "Details": "Data movement, transformation, validation, or orchestration inferred from parsed Talend metadata."},
            ]),
            use_container_width=True,
            hide_index=True,
        )

    with doc_tabs[1]:
        st.markdown("##### Technical Summary")
        rows = [
            {"Metric": "Components", "Value": len(components)},
            {"Metric": "tMap Components", "Value": len(tmaps)},
            {"Metric": "SQL Operations", "Value": len(sql_ops)},
            {"Metric": "Java Components", "Value": len(java_components)},
            {"Metric": "Child Jobs", "Value": len(dependencies.get("child_jobs", []) or [])},
            {"Metric": "Routines", "Value": len(dependencies.get("routines", []) or [])},
            {"Metric": "Contexts", "Value": len(dependencies.get("contexts", []) or [])},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with doc_tabs[2]:
        st.markdown("##### Migration Notes")
        notes = [
            {"Topic": "Complexity", "Note": f"{level} complexity with score {score}."},
            {"Topic": "Cloud Readiness", "Note": f"Cloud readiness is {readiness}."},
            {"Topic": "Effort", "Note": f"Estimated migration effort is {effort} hour(s) based on current complexity rules."},
            {"Topic": "Java", "Note": f"{len(java_components)} inline Java component(s) require review." if java_components else "No inline Java components detected."},
            {"Topic": "SQL", "Note": f"{len(sql_ops)} SQL operation(s) should be validated for target dialect compatibility." if sql_ops else "No executable SQL operations detected."},
        ]
        st.dataframe(pd.DataFrame(notes), use_container_width=True, hide_index=True)

    with doc_tabs[3]:
        st.markdown("##### Risks")
        rows = []
        for item in risk_factors:
            rows.append({"Severity": "REVIEW", "Source": "Complexity", "Risk": str(item)})
        for item in high_risks:
            rows.append({
                "Severity": item.get("risk") or item.get("severity") or "HIGH",
                "Source": item.get("type") or item.get("category") or "Enterprise Risk",
                "Risk": item.get("message") or item.get("issue") or item.get("description") or str(item),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.success("No high or critical documentation risks detected for this job.")

    with doc_tabs[4]:
        st.markdown("##### Recommendations")
        if job_recs:
            st.dataframe(
                pd.DataFrame([{
                    "Category": r.get("category", ""),
                    "Issue": r.get("issue", ""),
                    "Recommendation": r.get("fix") or r.get("recommendation", ""),
                    "Auto Fix": bool(r.get("auto_fix")),
                } for r in job_recs]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            fallback = [
                {"Category": "Validation", "Recommendation": "Validate source-to-target counts and key business rules after migration."},
                {"Category": "Testing", "Recommendation": "Use the preserved Testing tab to generate or review reconciliation checks."},
                {"Category": "Documentation", "Recommendation": "Keep TDD and Docs Hub exports aligned with the final migrated design."},
            ]
            st.dataframe(pd.DataFrame(fallback), use_container_width=True, hide_index=True)


PHASE8_EXPORT_SECTIONS = ["Overview", "Architecture", "Mapping", "Lineage", "SQL", "Java", "Documentation"]


def _phase8_cache_get(namespace: str, key: str, builder):
    """Session cache for expensive Job 360 export/read-model payloads."""
    root = st.session_state.setdefault("_phase8_cache", {})
    bucket = root.setdefault(namespace, {})
    if key not in bucket:
        bucket[key] = builder()
    return bucket[key]


def _phase8_md_table(rows: list[dict], headers: list[str]) -> str:
    if not rows:
        return "_No data available._"
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(out)


def _phase8_plain_text(sections: dict[str, str], title: str) -> str:
    return "\n\n".join([title, *[f"{name}\n{'=' * len(name)}\n{body}" for name, body in sections.items()]])


def _phase8_fallback_pdf(sections: dict[str, str], title: str) -> bytes:
    text = _phase8_plain_text(sections, title)
    lines = []
    for raw_line in text.splitlines()[:48]:
        line = re.sub(r"[^\x20-\x7E]", " ", raw_line)[:96]
        line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        lines.append(line)
    stream = "BT /F1 10 Tf 40 760 Td " + " T* ".join(f"({line}) Tj" for line in lines) + " ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('latin-1', 'replace'))} >> stream\n{stream}\nendstream endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1")))
        pdf += obj + "\n"
    xref_at = len(pdf.encode("latin-1"))
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF"
    return pdf.encode("latin-1", "replace")


def _phase8_fallback_docx(sections: dict[str, str], title: str) -> bytes:
    import io
    import zipfile
    import xml.sax.saxutils as xml_escape

    paras = [title]
    for name, body in sections.items():
        paras.append(name)
        paras.extend(body.splitlines()[:80])
    body_xml = "".join(
        f"<w:p><w:r><w:t>{xml_escape.escape(str(p))}</w:t></w:r></w:p>"
        for p in paras
        if str(p).strip()
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body_xml}<w:sectPr/></w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ))
        zf.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ))
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


def _phase8_fallback_html(sections: dict[str, str], title: str) -> bytes:
    body = [f"<h1>{html_lib.escape(title)}</h1>"]
    for name, content in sections.items():
        body.append(f"<h2>{html_lib.escape(name)}</h2>")
        body.append(f"<pre>{html_lib.escape(content)}</pre>")
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html_lib.escape(title)}</title>"
        "<style>body{font-family:Arial,sans-serif;margin:32px;color:#111827;}"
        "pre{white-space:pre-wrap;background:#f9fafb;border:1px solid #e5e7eb;padding:12px;}"
        "h1,h2{color:#1f2937;}</style></head><body>"
        + "\n".join(body)
        + "</body></html>"
    )
    return html.encode("utf-8")


def _phase8_export_sections(
    job: dict,
    jd: dict,
    inv: dict,
    all_recs: list[dict],
    sql_ops: list[dict],
    job_name: str,
    cached_export: dict,
) -> dict[str, str]:
    def _build() -> dict[str, str]:
        components = jd.get("components", [])
        complexity = job.get("complexity", {})
        dependencies = job.get("dependencies", {})
        level = complexity.get("complexity") or complexity.get("level") or cached_export.get("level", "LOW")
        score = complexity.get("score", cached_export.get("score", "—"))
        sources = cached_export.get("sources", []) or [s.get("name", "") for s in inv.get("sources", []) if s.get("name")]
        targets = cached_export.get("targets", []) or [t.get("name", "") for t in inv.get("targets", []) if t.get("name")]
        flow_steps = cached_export.get("flow_steps", [])
        job_recs = [r for r in all_recs if r.get("job_name") == job_name]
        java_payload = _phase8_cache_get("java_analysis", job_name, lambda: analyze_java_logic(job))

        metadata_rows = [
            {"Metric": "Job Name", "Value": job_name},
            {"Metric": "Talend Version", "Value": jd.get("talend_version", "—")},
            {"Metric": "Job Version", "Value": jd.get("job_version", "—")},
            {"Metric": "Components", "Value": len(components)},
            {"Metric": "Sources", "Value": len(sources)},
            {"Metric": "Targets", "Value": len(targets)},
            {"Metric": "Complexity", "Value": f"{level} ({score})"},
        ]
        comp_rows = [
            {
                "Component": c.get("unique_name", ""),
                "Type": c.get("component_type", ""),
                "Purpose": c.get("purpose", ""),
            }
            for c in components[:80]
        ]
        mapping_rows = [
            {"Source": s or "—", "Target": t or "—"}
            for s in (sources or ["—"])
            for t in (targets or ["—"])
        ][:80]
        sql_rows = [
            {
                "Component": op.get("component", ""),
                "DB": op.get("db_type", ""),
                "Query": _clean_sql(op.get("query", ""))[:240],
            }
            for op in sql_ops
        ]
        dep_rows = []
        for key, label in (("parent_jobs", "Upstream"), ("child_jobs", "Downstream"), ("routines", "Routine"), ("contexts", "Context")):
            for value in dependencies.get(key, []) or []:
                dep_rows.append({"Type": label, "Name": value})
        rec_rows = [
            {
                "Category": r.get("category", ""),
                "Issue": r.get("issue", ""),
                "Recommendation": r.get("fix") or r.get("recommendation", ""),
                "Auto Fix": bool(r.get("auto_fix")),
            }
            for r in job_recs
        ]
        java_rows = java_payload.get("java_inventory", [])

        documentation_notes = [
            {"Section": "Business Summary", "Content": f"{job_name} moves data from {', '.join(sources[:6]) or 'detected sources'} to {', '.join(targets[:6]) or 'detected targets'}."},
            {"Section": "Technical Summary", "Content": f"{len(components)} components, {len(sql_ops)} SQL operation(s), {java_payload.get('java_component_count', 0)} Java component(s)."},
            {"Section": "Migration Notes", "Content": f"{level} complexity with estimated {cached_export.get('effort', '—')}h effort."},
            {"Section": "Risks", "Content": ", ".join(complexity.get("risk_factors", []) or []) or "No explicit risk factors detected."},
        ]

        return {
            "Overview": "# Overview\n\n" + _phase8_md_table(metadata_rows, ["Metric", "Value"]),
            "Architecture": (
                "# Architecture\n\n## Component Inventory\n\n"
                + _phase8_md_table(comp_rows, ["Component", "Type", "Purpose"])
                + "\n\n## Dependencies\n\n"
                + _phase8_md_table(dep_rows, ["Type", "Name"])
            ),
            "Mapping": "# Mapping\n\n" + _phase8_md_table(mapping_rows, ["Source", "Target"]),
            "Lineage": (
                "# Lineage\n\n"
                + "## Source / Target Lineage\n\n"
                + _phase8_md_table(mapping_rows, ["Source", "Target"])
                + "\n\n## Flow Steps\n\n"
                + "\n".join(f"- {title}: {detail}" for _, title, detail in flow_steps)
            ),
            "SQL": "# SQL Analysis\n\n" + _phase8_md_table(sql_rows, ["Component", "DB", "Query"]),
            "Java": (
                "# Java Analysis\n\n"
                + _phase8_md_table(java_rows, ["Component", "Type", "LOC", "Complexity", "Complexity Score", "Risk", "Routines", "External Libraries"])
                + "\n\n## AI Explanation\n\n"
                + java_payload.get("ai_explanation", "No Java explanation available.")
                + "\n\n## Recommendations\n\n"
                + _phase8_md_table(java_payload.get("recommendations", []), ["Component", "priority", "category", "recommendation"])
            ),
            "Documentation": (
                "# Documentation\n\n"
                + _phase8_md_table(documentation_notes, ["Section", "Content"])
                + "\n\n## Recommendations\n\n"
                + (_phase8_md_table(rec_rows, ["Category", "Issue", "Recommendation", "Auto Fix"]) if rec_rows else "- Validate TDD, Docs Hub, and Testing artifacts before sign-off.")
            ),
        }

    return _phase8_cache_get("documentation", job_name, _build)


def _phase8_export_bytes(
    sections: dict[str, str],
    selected_sections: list[str],
    fmt: str,
    title: str,
) -> tuple[bytes, str, str]:
    from app.ui.export_assets import AssetManifest
    from app.ui.export_writers import docx_bytes, html_bytes, pdf_bytes

    chosen = {name: sections[name] for name in selected_sections if name in sections}
    if not chosen:
        chosen = sections
    manifests = {name: AssetManifest(doc_type=name) for name in chosen}
    safe_title = re.sub(r"[^\w\-]+", "_", title).strip("_") or "Job360_Export"

    if fmt == "PDF":
        try:
            data = pdf_bytes(chosen, manifests, title)
            if not data or data.startswith(b"PDF unavailable"):
                data = _phase8_fallback_pdf(chosen, title)
        except Exception:
            data = _phase8_fallback_pdf(chosen, title)
        return data, f"{safe_title}.pdf", "application/pdf"
    if fmt == "DOCX":
        try:
            data = docx_bytes(chosen, manifests, title)
        except Exception:
            data = _phase8_fallback_docx(chosen, title)
        return data, f"{safe_title}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if fmt == "HTML":
        try:
            data = html_bytes(chosen, manifests, title)
        except Exception:
            data = _phase8_fallback_html(chosen, title)
        return data, f"{safe_title}.html", "text/html"
    if fmt == "ZIP":
        import io
        import json
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{safe_title}.pdf", _phase8_export_bytes(sections, selected_sections, "PDF", title)[0])
            zf.writestr(f"{safe_title}.docx", _phase8_export_bytes(sections, selected_sections, "DOCX", title)[0])
            zf.writestr(f"{safe_title}.html", _phase8_export_bytes(sections, selected_sections, "HTML", title)[0])
            zf.writestr("manifest.json", json.dumps({"title": title, "sections": list(chosen)}, indent=2))
        return buf.getvalue(), f"{safe_title}.zip", "application/zip"
    raise ValueError(f"Unsupported export format: {fmt}")


def _render_phase8_export_center(job, jd, inv, all_recs, sql_ops, job_name, cached_export) -> None:
    st.markdown("#### Export Center")
    st.caption("Lazy export generation from cached metadata, SQL analysis, Java analysis, lineage, and documentation payloads.")

    sections = _phase8_export_sections(job, jd, inv, all_recs, sql_ops, job_name, cached_export)
    c1, c2 = st.columns([2, 1])
    with c1:
        selected = st.multiselect(
            "Sections",
            PHASE8_EXPORT_SECTIONS,
            default=PHASE8_EXPORT_SECTIONS,
            key=f"phase8_export_sections_{job_name}",
        )
    with c2:
        fmt = st.selectbox("Format", ["PDF", "DOCX", "HTML", "ZIP"], key=f"phase8_export_format_{job_name}")

    cache_key = f"phase8_export_payload_{job_name}_{fmt}_{hashlib.sha1('|'.join(selected).encode('utf-8')).hexdigest()[:10]}"
    if st.button("Prepare Export", key=f"phase8_prepare_export_{job_name}", type="primary", use_container_width=True):
        st.session_state[cache_key] = _phase8_export_bytes(
            sections,
            selected,
            fmt,
            f"Job 360 Export - {job_name}",
        )

    if cache_key in st.session_state:
        data, filename, mime = st.session_state[cache_key]
        st.download_button(
            f"Download {fmt}",
            data=data,
            file_name=filename,
            mime=mime,
            key=f"phase8_download_{job_name}_{fmt}",
            use_container_width=True,
        )
    else:
        st.info("Choose sections and format, then prepare the export. Generation runs only on demand.")

    with st.expander("Phase 8 Performance Cache", expanded=False):
        cache = st.session_state.get("_phase8_cache", {})
        rows = [{"Cache": name, "Entries": len(values)} for name, values in sorted(cache.items())]
        rows.extend([
            {"Cache": "metadata", "Entries": 1 if inv else 0},
            {"Cache": "sql_analysis", "Entries": 1 if sql_ops is not None else 0},
            {"Cache": "lineage", "Entries": 1},
        ])
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("Repository scans, XML parsing, lineage generation, and document assembly are reused from session/Phase 1C caches.")

def _cloud_rag(cr: dict) -> str:
    """Get RAG status from a cloud_readiness dict (supports RAG status fields)."""
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    return _score_to_rag(cr.get("score", 0))


_SKIP_FLOW_COMPONENTS = {
    "tLogRow", "tLogCatcher", "tDie", "tWarn", "tStatCatcher",
    "tPrejob", "tPostjob", "tFlowToIterate", "tIterateToFlow",
}


def _clean_sql(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", str(sql or ""), flags=re.DOTALL)
    sql = re.sub(r"--.*?$", " ", sql, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", sql).strip()


def _sql_tables(pattern: str, sql: str) -> list[str]:
    return sorted({
        t.strip('"[]`').split()[-1]
        for t in re.findall(pattern, sql, flags=re.IGNORECASE)
        if t and not t.upper().startswith(("SELECT", "WHERE", "ON"))
    })


def _detect_query_type(sql: str) -> str:
    upper = sql.upper().strip()
    if re.search(r"\bON\s+(?:DUPLICATE\s+KEY|CONFLICT)\b", upper):
        return "UPSERT"
    for qtype in ("MERGE", "INSERT", "UPDATE", "DELETE", "SELECT"):
        if upper.startswith(qtype):
            return qtype
    return "SQL"


def _extract_business_logic(sql: str) -> dict:
    """Extract conditional business logic expressions from SQL."""
    upper = sql.upper()

    # CASE WHEN … THEN … (ELSE …) END
    case_blocks = []
    for m in re.finditer(r"\bCASE\b(.+?)\bEND\b", sql, flags=re.IGNORECASE | re.DOTALL):
        block = re.sub(r"\s+", " ", m.group(0)).strip()
        case_blocks.append(block[:200] + ("…" if len(block) > 200 else ""))

    # IF(condition, true_val, false_val)
    if_exprs = []
    for m in re.finditer(r"\bIF\s*\((.+?)\)", sql, flags=re.IGNORECASE | re.DOTALL):
        expr = re.sub(r"\s+", " ", m.group(0)).strip()
        if_exprs.append(expr[:200] + ("…" if len(expr) > 200 else ""))

    # DECODE(col, val1, res1, …, default)
    decode_exprs = []
    for m in re.finditer(r"\bDECODE\s*\((.+?)\)", sql, flags=re.IGNORECASE | re.DOTALL):
        expr = re.sub(r"\s+", " ", m.group(0)).strip()
        decode_exprs.append(expr[:200] + ("…" if len(expr) > 200 else ""))

    # NVL(expr, replacement)
    nvl_exprs = []
    for m in re.finditer(r"\bNVL\s*\((.+?)\)", sql, flags=re.IGNORECASE | re.DOTALL):
        expr = re.sub(r"\s+", " ", m.group(0)).strip()
        nvl_exprs.append(expr[:200] + ("…" if len(expr) > 200 else ""))

    # COALESCE(expr1, expr2, …)
    coalesce_exprs = []
    for m in re.finditer(r"\bCOALESCE\s*\((.+?)\)", sql, flags=re.IGNORECASE | re.DOTALL):
        expr = re.sub(r"\s+", " ", m.group(0)).strip()
        coalesce_exprs.append(expr[:200] + ("…" if len(expr) > 200 else ""))

    return {
        "case_when": case_blocks,
        "if_expr": if_exprs,
        "decode": decode_exprs,
        "nvl": nvl_exprs,
        "coalesce": coalesce_exprs,
    }


def _analyze_sql_query(op: dict, index: int) -> dict:
    sql = _clean_sql(op.get("query", ""))
    upper = sql.upper()
    qtype = _detect_query_type(sql)
    source_tables = _sql_tables(r"\b(?:FROM|JOIN|USING)\s+([A-Za-z0-9_\.\[\]\"`]+)", sql)
    target_tables = []
    if qtype in ("INSERT", "UPSERT"):
        target_tables = _sql_tables(r"\bINTO\s+([A-Za-z0-9_\.\[\]\"`]+)", sql)
    elif qtype == "UPDATE":
        target_tables = _sql_tables(r"\bUPDATE\s+([A-Za-z0-9_\.\[\]\"`]+)", sql)
    elif qtype == "DELETE":
        target_tables = _sql_tables(r"\bDELETE\s+FROM\s+([A-Za-z0-9_\.\[\]\"`]+)", sql)
    elif qtype == "MERGE":
        target_tables = _sql_tables(r"\bMERGE\s+INTO\s+([A-Za-z0-9_\.\[\]\"`]+)", sql)
    elif qtype == "SELECT":
        target_tables = _sql_tables(r"\bINTO\s+([A-Za-z0-9_\.\[\]\"`]+)", sql)

    _join_pattern = re.findall(
        r"\b((?:LEFT\s+OUTER|RIGHT\s+OUTER|FULL\s+OUTER|LEFT|RIGHT|FULL|INNER|CROSS|NATURAL)?\s*JOIN)\s+"
        r"([A-Za-z0-9_\.\[\]\"`]+)\s+.*?\bON\s+(.+?)(?=\b(?:LEFT|RIGHT|FULL|INNER|CROSS|NATURAL)?\s*JOIN\b|\bWHERE\b|\bGROUP BY\b|\bORDER BY\b|$)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Identify the FROM table (left-hand side of the first join)
    _from_match = re.search(r"\bFROM\s+([A-Za-z0-9_\.\[\]\"`]+)", sql, flags=re.IGNORECASE)
    _from_table = _from_match.group(1) if _from_match else "unknown"
    joins = [
        {
            "join_type": re.sub(r"\s+", " ", jtype.strip()).upper() if jtype.strip() else "JOIN",
            "tables": f"{_from_table} ↔ {tbl.strip(chr(34))}",
            "condition": cond.strip(),
        }
        for jtype, tbl, cond in _join_pattern
    ]
    # Legacy flat list for backward-compat with summary/business-rules helpers
    _joins_flat = [f"{j['tables']} ON {j['condition']}" for j in joins]
    filters = [
        cond.strip()
        for cond in re.findall(
            r"\bWHERE\s+(.+?)(?=\bGROUP BY\b|\bORDER BY\b|\bHAVING\b|\bQUALIFY\b|$)",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
    ]
    aggregations = sorted(set(re.findall(r"\b(COUNT|SUM|AVG|MIN|MAX|GROUP BY|HAVING)\b", upper)))
    window_functions = sorted(set(re.findall(r"\b(ROW_NUMBER|RANK|DENSE_RANK|LAG|LEAD|NTILE|OVER|PARTITION BY)\b", upper)))
    subqueries = len(re.findall(r"\(\s*SELECT\b", upper))
    match_merge_logic = bool(re.search(r"\b(MERGE|MATCHED|NOT\s+MATCHED|ON\s+DUPLICATE|ON\s+CONFLICT)\b", upper))
    deduplication_logic = bool(re.search(r"\b(DISTINCT|ROW_NUMBER|DENSE_RANK|DUPLICATE|DEDUP|PARTITION BY)\b", upper))
    surrogate_key_generation = bool(re.search(r"\b(NEXTVAL|SEQUENCE|IDENTITY|UUID|GUID|SURROGATE|ROW_NUMBER)\b", upper))
    cdc_logic = bool(re.search(r"\b(CDC|CHANGE|CHANGED|OP_TYPE|OPERATION|EFFECTIVE_FROM|EFFECTIVE_TO|UPDATED_AT|LAST_UPDATE|DELETE_FLAG)\b", upper))

    feature_count = sum([
        bool(source_tables), bool(target_tables), bool(joins), bool(filters),
        bool(aggregations), bool(window_functions), bool(subqueries),
        match_merge_logic, deduplication_logic, surrogate_key_generation, cdc_logic,
    ])
    confidence = min(96, 58 + feature_count * 4 + (8 if qtype != "SQL" else 0))

    actions = []
    if source_tables:
        actions.append(f"reads data from {', '.join(source_tables)}")
    if joins:
        actions.append("joins related datasets")
    if filters:
        actions.append("applies filtering rules")
    if aggregations:
        actions.append("calculates aggregate metrics")
    if window_functions:
        actions.append("uses windowed ranking or analytic logic")
    if deduplication_logic:
        actions.append("handles deduplication")
    if match_merge_logic:
        actions.append("applies match or merge rules")
    if surrogate_key_generation:
        actions.append("generates technical keys")
    if cdc_logic:
        actions.append("supports change-data-capture handling")
    if target_tables:
        actions.append(f"produces output for {', '.join(target_tables)}")

    business_purpose = (
        f"This {qtype.lower()} query " + ", ".join(actions) + "."
        if actions else f"This {qtype.lower()} query performs database processing based on the detected SQL structure."
    )

    # ── SQL Complexity scoring ────────────────────────────────────────────
    _sql_functions = sorted(set(re.findall(
        r"\b(COALESCE|NVL|DECODE|CASE|IIF|IF|NULLIF|CAST|CONVERT|TO_DATE|TO_CHAR|TO_NUMBER"
        r"|SUBSTR|SUBSTRING|TRIM|LTRIM|RTRIM|REPLACE|UPPER|LOWER|LENGTH|LEN|CONCAT"
        r"|DATEDIFF|DATEADD|DATE_TRUNC|EXTRACT|YEAR|MONTH|DAY|NOW|SYSDATE|GETDATE"
        r"|COUNT|SUM|AVG|MIN|MAX|RANK|ROW_NUMBER|DENSE_RANK|LAG|LEAD|NTILE"
        r"|LISTAGG|STRING_AGG|GROUP_CONCAT|PIVOT|UNPIVOT|ROLLUP|CUBE|GROUPING SETS)\b",
        sql, flags=re.IGNORECASE,
    )))
    _cx_score = (
        len(source_tables) * 1
        + len(joins) * 2
        + subqueries * 3
        + len(_sql_functions) * 1
        + (2 if window_functions else 0)
        + (2 if match_merge_logic else 0)
        + (1 if deduplication_logic else 0)
        + (1 if cdc_logic else 0)
    )
    if _cx_score <= 4:
        _cx_level = "LOW"
    elif _cx_score <= 10:
        _cx_level = "MEDIUM"
    else:
        _cx_level = "HIGH"

    return {
        "index": index,
        "component": op.get("component", ""),
        "db_type": op.get("db_type", ""),
        "query": sql,
        "query_type": qtype,
        "source_tables": source_tables,
        "target_tables": target_tables,
        "joins": _joins_flat,
        "joins_detail": joins,
        "aggregations": aggregations,
        "filters": filters,
        "window_functions": window_functions,
        "subqueries": subqueries,
        "match_merge_logic": match_merge_logic,
        "deduplication_logic": deduplication_logic,
        "surrogate_key_generation": surrogate_key_generation,
        "cdc_logic": cdc_logic,
        "business_purpose": business_purpose,
        "confidence": confidence,
        "business_logic": _extract_business_logic(sql),
        "sql_functions": _sql_functions,
        "complexity_score": _cx_score,
        "complexity_level": _cx_level,
    }


def _plain_english_summary(analysis: dict) -> str:
    """Generate a plain English narrative sentence for a SQL query analysis."""
    qtype = analysis.get("query_type", "SQL")
    sources = analysis.get("source_tables", [])
    targets = analysis.get("target_tables", [])
    joins = analysis.get("joins", [])
    filters = analysis.get("filters", [])
    aggregations = analysis.get("aggregations", [])
    window_functions = analysis.get("window_functions", [])
    match_merge = analysis.get("match_merge_logic", False)
    dedup = analysis.get("deduplication_logic", False)
    cdc = analysis.get("cdc_logic", False)
    surrogate = analysis.get("surrogate_key_generation", False)
    subqueries = analysis.get("subqueries", 0)

    parts = []
    if qtype == "SELECT":
        parts.append("This query retrieves data")
    elif qtype == "INSERT":
        parts.append("This query inserts records")
    elif qtype == "UPDATE":
        parts.append("This query updates existing records")
    elif qtype == "DELETE":
        parts.append("This query deletes records")
    elif qtype == "MERGE":
        parts.append("This query merges (upserts) records")
    else:
        parts.append("This query performs SQL processing")

    if sources:
        parts.append(f"from {', '.join(sources)}")
    if joins:
        parts.append(f"joined across {len(joins)} relationship(s)")
    if filters:
        parts.append("with conditional filtering applied")
    if aggregations:
        agg_list = ", ".join(aggregations)
        parts.append(f"computing aggregates ({agg_list})")
    if window_functions:
        parts.append("using window/analytic functions")
    if subqueries:
        parts.append(f"including {subqueries} subquer{'y' if subqueries == 1 else 'ies'}")
    if dedup:
        parts.append("with deduplication logic")
    if match_merge:
        parts.append("applying match-and-merge rules")
    if cdc:
        parts.append("handling change-data-capture patterns")
    if surrogate:
        parts.append("generating surrogate/technical keys")
    if targets:
        parts.append(f"and writes results to {', '.join(targets)}")

    return " ".join(parts) + "."


def _business_rules_list(analysis: dict) -> list[str]:
    """Derive a list of business rule statements from a SQL query analysis."""
    rules = []
    joins = analysis.get("joins", [])
    filters = analysis.get("filters", [])
    aggregations = analysis.get("aggregations", [])
    window_functions = analysis.get("window_functions", [])
    match_merge = analysis.get("match_merge_logic", False)
    dedup = analysis.get("deduplication_logic", False)
    cdc = analysis.get("cdc_logic", False)
    surrogate = analysis.get("surrogate_key_generation", False)
    subqueries = analysis.get("subqueries", 0)
    sources = analysis.get("source_tables", [])
    targets = analysis.get("target_tables", [])

    if sources:
        rules.append(f"Data must be sourced from: {', '.join(sources)}.")
    if targets:
        rules.append(f"Output must be written to: {', '.join(targets)}.")
    for join in joins:
        rules.append(f"Records must be joined: {join}.")
    for f in filters:
        short = f[:120] + "..." if len(f) > 120 else f
        rules.append(f"Only records matching the condition are processed: {short}.")
    if aggregations:
        rules.append(f"Aggregate functions applied: {', '.join(aggregations)}.")
    if window_functions:
        rules.append(f"Window/analytic functions used: {', '.join(window_functions)}.")
    if subqueries:
        rules.append(f"Query contains {subqueries} nested subquer{'y' if subqueries == 1 else 'ies'} for additional filtering or lookup.")
    if dedup:
        rules.append("Duplicate records must be identified and removed or ranked.")
    if match_merge:
        rules.append("Records are matched against a target; inserts occur for new records, updates for existing ones.")
    if cdc:
        rules.append("Change-data-capture columns (e.g. operation type, effective dates) govern record lifecycle.")
    if surrogate:
        rules.append("Technical/surrogate keys are generated as part of this operation.")
    if not rules:
        rules.append("No specific business rules detected from SQL structure.")
    return rules


@st.cache_data(show_spinner=False)
def _generate_sql_business_context(job_name: str, query_signature: str, sql_ops: tuple[tuple[str, str, str], ...]) -> dict:
    analyses = [
        _analyze_sql_query({"component": c, "db_type": d, "query": q}, idx)
        for idx, (c, d, q) in enumerate(sql_ops, start=1)
        if _clean_sql(q)
    ]
    sources = sorted({t for a in analyses for t in a["source_tables"]})
    targets = sorted({t for a in analyses for t in a["target_tables"]})
    query_types = sorted({a["query_type"] for a in analyses})
    has_joins = any(a["joins"] for a in analyses)
    has_aggregations = any(a["aggregations"] for a in analyses)
    has_filters = any(a["filters"] for a in analyses)
    has_merge = any(a["match_merge_logic"] for a in analyses)
    has_dedup = any(a["deduplication_logic"] for a in analyses)
    has_cdc = any(a["cdc_logic"] for a in analyses)
    avg_conf = int(sum(a["confidence"] for a in analyses) / len(analyses)) if analyses else 0

    actions = []
    if sources:
        actions.append(f"reads data from {', '.join(sources)}")
    if has_joins:
        actions.append("joins datasets")
    if has_filters:
        actions.append("filters records")
    if has_aggregations:
        actions.append("calculates metrics")
    if has_merge:
        actions.append("applies match or merge logic")
    if has_dedup:
        actions.append("deduplicates records")
    if has_cdc:
        actions.append("handles changed data")
    if targets:
        actions.append(f"writes curated output to {', '.join(targets)}")

    purpose = (
        f"This job executes {len(analyses)} SQL quer{'y' if len(analyses) == 1 else 'ies'} "
        f"({', '.join(query_types)}) and " + ", ".join(actions) + "."
        if actions else "No SQL business purpose could be generated because no executable SQL query text was detected."
    )
    flow = {
        "sources": sources or ["Detected SQL input"],
        "transformation": [],
        "targets": targets or ["Detected SQL output"],
    }
    for label, present in (
        ("Joins", has_joins),
        ("Aggregations", has_aggregations),
        ("Filters", has_filters),
        ("Match/Merge Logic", has_merge),
        ("Deduplication Logic", has_dedup),
        ("CDC Logic", has_cdc),
    ):
        if present:
            flow["transformation"].append(label)
    if not flow["transformation"]:
        flow["transformation"].append("SQL execution logic")

    summary = []
    if sources:
        summary.append(f"Reads data from {', '.join(sources)}.")
    if has_joins:
        summary.append("Joins source datasets.")
    if has_filters:
        summary.append("Filters records using detected WHERE logic.")
    if has_aggregations:
        summary.append("Calculates aggregate metrics.")
    if has_merge:
        summary.append("Applies match, merge, or upsert rules.")
    if has_dedup:
        summary.append("Detects or removes duplicate records.")
    if targets:
        summary.append(f"Produces output for {', '.join(targets)}.")

    return {"purpose": purpose, "flow": flow, "summary": summary, "confidence": avg_conf, "queries": analyses}


def _flow_icon(ctype: str) -> str:
    c = (ctype or "").lower()
    if c.endswith("input") or "input" in c:
        return "📥"
    if c.endswith("output") or "output" in c:
        return "📤"
    if "map" in c:
        return "🔀"
    if "java" in c or "beanshell" in c:
        return "⚙️"
    if "filter" in c or "schema" in c:
        return "🔍"
    if "runjob" in c:
        return "▶️"
    if "joblet" in c:
        return "🧩"
    if "file" in c and any(k in c for k in ("delete", "exist", "copy", "list")):
        return "🗂️"
    return "⬜"


def _friendly_component_name(ctype: str) -> str:
    text = str(ctype or "")
    if text.startswith("t"):
        text = text[1:]
    words = re.findall(r"[A-Z][a-z0-9]*|[A-Z]+(?![a-z])|[0-9]+", text)
    return " ".join(words) if words else text


def _step_detail(c: dict) -> str:
    params = component_parameters(c)
    for key in ("TABLE", "FILENAME", "FILE_NAME", "QUERY", "PROCESS", "JOBLET", "CONNECTION"):
        val = params.get(key)
        if val:
            val = normalize_name(val) if key != "QUERY" else val
            if val:
                return val[:60]
    return c.get("unique_name", "")


def _render_mermaid(mermaid_code: str, height: int = 420) -> None:
    """Render a Mermaid-style flowchart diagram, fully offline (no CDN)."""
    render_mermaid_diagram(mermaid_code, height=height)



def _build_flow_steps(jd: dict) -> list:
    steps = []
    prev_key = None
    for c in jd.get("components", []):
        ctype = c.get("component_type", "Unknown")
        if ctype in _SKIP_FLOW_COMPONENTS:
            continue
        detail = _step_detail(c)
        key = (ctype, detail)
        if key == prev_key:
            continue
        prev_key = key
        steps.append((_flow_icon(ctype), _friendly_component_name(ctype), detail or ctype))
    if not steps:
        steps = [("⬜", "No Components", "No components found in this job")]
    return steps



# ── SQL Performance: heavy-function catalogue (constant, used in tab render) ──
_SQL_HEAVY_FUNCTIONS: dict[str, str] = {
    "ROW_NUMBER": "window function (ROW_NUMBER)",
    "RANK": "window function (RANK)",
    "DENSE_RANK": "window function (DENSE_RANK)",
    "LAG": "window function (LAG)",
    "LEAD": "window function (LEAD)",
    "NTILE": "window function (NTILE)",
    "LISTAGG": "aggregation function (LISTAGG)",
    "STRING_AGG": "aggregation function (STRING_AGG)",
    "GROUP_CONCAT": "aggregation function (GROUP_CONCAT)",
    "PIVOT": "PIVOT operation",
    "UNPIVOT": "UNPIVOT operation",
    "ROLLUP": "ROLLUP grouping",
    "CUBE": "CUBE grouping",
    "XMLAGG": "XML aggregation",
    "XMLELEMENT": "XML generation",
}


def _explain_sql_line(line: str) -> str:
    """Return a business-language explanation for a single SQL line."""
    s = line.strip()
    u = s.upper()

    # SELECT clause
    if re.match(r"^SELECT\b", u):
        cols = re.sub(r"^SELECT\s+(DISTINCT\s+)?", "", s, flags=re.IGNORECASE).strip().rstrip(",")
        distinct = "unique " if re.search(r"\bDISTINCT\b", u) else ""
        if cols in ("*", ""):
            return f"Retrieve {distinct}all fields from the dataset."
        col_list = [c.strip() for c in cols.split(",") if c.strip()]
        if len(col_list) <= 4:
            return f"Retrieve {distinct}the following fields: {', '.join(col_list)}."
        return f"Retrieve {distinct}{len(col_list)} fields including {', '.join(col_list[:3])} and more."

    # FROM clause
    if re.match(r"^FROM\b", u):
        tbl = re.sub(r"^FROM\s+", "", s, flags=re.IGNORECASE).strip().split()[0]
        return f"Pull data from the **{tbl}** table."

    # JOIN types
    join_m = re.match(
        r"^(LEFT\s+(?:OUTER\s+)?JOIN|RIGHT\s+(?:OUTER\s+)?JOIN|FULL\s+(?:OUTER\s+)?JOIN|INNER\s+JOIN|CROSS\s+JOIN|JOIN)\s+(\S+)",
        s, flags=re.IGNORECASE
    )
    if join_m:
        jtype_raw = join_m.group(1).upper()
        jtbl = join_m.group(2)
        jtype_map = {
            "LEFT": "include all records from the main dataset and match where available from",
            "LEFT OUTER": "include all records from the main dataset and match where available from",
            "RIGHT": "include all records from",
            "RIGHT OUTER": "include all records from",
            "FULL": "include all records from both sides and",
            "FULL OUTER": "include all records from both sides and",
            "INNER": "match only records that exist in both the main dataset and",
            "CROSS": "combine every row from the main dataset with every row from",
        }
        jkey = next((k for k in jtype_map if jtype_raw.startswith(k)), "JOIN")
        return f"Link to **{jtbl}**: {jtype_map.get(jkey, 'join with')} **{jtbl}**."

    # ON clause
    if re.match(r"^ON\b", u):
        cond = re.sub(r"^ON\s+", "", s, flags=re.IGNORECASE).strip()
        return f"Match records where **{cond}**."

    # WHERE clause
    if re.match(r"^WHERE\b", u):
        cond = re.sub(r"^WHERE\s+", "", s, flags=re.IGNORECASE).strip().rstrip(",")
        return f"Filter to only include records where **{cond}**."

    # AND / OR continuation
    if re.match(r"^(AND|OR)\b", u):
        cond = re.sub(r"^(AND|OR)\s+", "", s, flags=re.IGNORECASE).strip()
        connector = "Also require" if u.startswith("AND") else "Or alternatively include records where"
        return f"{connector} **{cond}**."

    # GROUP BY
    if re.match(r"^GROUP\s+BY\b", u):
        cols = re.sub(r"^GROUP\s+BY\s+", "", s, flags=re.IGNORECASE).strip()
        return f"Group the results by **{cols}** to produce summary totals or aggregates."

    # HAVING
    if re.match(r"^HAVING\b", u):
        cond = re.sub(r"^HAVING\s+", "", s, flags=re.IGNORECASE).strip()
        return f"After grouping, keep only groups where **{cond}**."

    # ORDER BY
    if re.match(r"^ORDER\s+BY\b", u):
        cols = re.sub(r"^ORDER\s+BY\s+", "", s, flags=re.IGNORECASE).strip()
        return f"Sort the final results by **{cols}**."

    # INSERT INTO
    if re.match(r"^INSERT\s+INTO\b", u):
        tbl = re.sub(r"^INSERT\s+INTO\s+", "", s, flags=re.IGNORECASE).strip().split()[0]
        return f"Write new records into the **{tbl}** table."

    # UPDATE
    if re.match(r"^UPDATE\b", u):
        tbl = re.sub(r"^UPDATE\s+", "", s, flags=re.IGNORECASE).strip().split()[0]
        return f"Update existing records in the **{tbl}** table."

    # SET
    if re.match(r"^SET\b", u):
        vals = re.sub(r"^SET\s+", "", s, flags=re.IGNORECASE).strip()
        return f"Apply the following changes: **{vals}**."

    # DELETE
    if re.match(r"^DELETE\b", u):
        return "Remove records from the target table based on the conditions below."

    # MERGE INTO
    if re.match(r"^MERGE\b", u):
        tbl = re.findall(r"\bINTO\s+(\S+)", s, flags=re.IGNORECASE)
        tbl_name = tbl[0] if tbl else "the target table"
        return f"Synchronise records into **{tbl_name}** — insert new ones and update existing ones."

    # WHEN MATCHED / WHEN NOT MATCHED
    if re.match(r"^WHEN\s+MATCHED\b", u):
        return "For records that already exist in the target, apply the update below."
    if re.match(r"^WHEN\s+NOT\s+MATCHED\b", u):
        return "For records that do not yet exist in the target, insert them."

    # WITH (CTE)
    if re.match(r"^WITH\b", u):
        cte = re.sub(r"^WITH\s+", "", s, flags=re.IGNORECASE).strip().split()[0]
        return f"Define a temporary named dataset called **{cte}** to simplify the query below."

    # CASE / WHEN / THEN / ELSE / END
    if re.match(r"^CASE\b", u):
        return "Begin a conditional rule: evaluate each condition in order and return the matching result."
    if re.match(r"^WHEN\b", u):
        cond = re.sub(r"^WHEN\s+", "", s, flags=re.IGNORECASE).split("THEN")[0].strip()
        return f"If **{cond}**, then …"
    if re.match(r"^THEN\b", u):
        val = re.sub(r"^THEN\s+", "", s, flags=re.IGNORECASE).strip()
        return f"… return **{val}**."
    if re.match(r"^ELSE\b", u):
        val = re.sub(r"^ELSE\s+", "", s, flags=re.IGNORECASE).strip()
        return f"For all other cases, return **{val}**."
    if re.match(r"^END\b", u):
        return "End of the conditional rule."

    # UNION / INTERSECT / EXCEPT
    if re.match(r"^UNION\s+ALL\b", u):
        return "Combine all results from the next query, including duplicates."
    if re.match(r"^UNION\b", u):
        return "Combine results from the next query, removing duplicate rows."
    if re.match(r"^INTERSECT\b", u):
        return "Keep only records that appear in both result sets."
    if re.match(r"^EXCEPT\b", u):
        return "Exclude records from the first result set that also appear in the second."

    # LIMIT / TOP / FETCH
    if re.match(r"^LIMIT\b", u) or re.match(r"^FETCH\b", u):
        n = re.findall(r"\d+", s)
        return f"Return only the first {n[0] if n else 'N'} records."

    # PARTITION BY
    if re.match(r"^PARTITION\s+BY\b", u):
        cols = re.sub(r"^PARTITION\s+BY\s+", "", s, flags=re.IGNORECASE).strip()
        return f"Divide the data into independent groups by **{cols}** before applying the window calculation."

    # OVER
    if re.match(r"^OVER\b", u):
        return "Apply the preceding function across a defined window of rows rather than the whole dataset."

    # VALUES
    if re.match(r"^VALUES\b", u):
        return "Specify the data values to be inserted."

    # INTO (standalone, e.g. SELECT INTO)
    if re.match(r"^INTO\b", u):
        tbl = re.sub(r"^INTO\s+", "", s, flags=re.IGNORECASE).strip().split()[0]
        return f"Store the query results into **{tbl}**."

    # Comments
    if s.startswith("--") or s.startswith("/*"):
        return f"Developer note: {s.lstrip('/-* ').rstrip('*/ ')}"

    # Closing parenthesis or punctuation-only lines
    if re.match(r"^[);,]+$", s):
        return "End of clause or sub-expression."

    # Fallback — return the line itself with a generic note
    return f"SQL clause: `{s[:120]}{'…' if len(s) > 120 else ''}`"



def render_job_analysis_page():
    all_jobs = st.session_state.get("last_analysis_jobs", [])

    if not all_jobs:
        page_header("🔍", "Job 360 Analysis", "No job selected")
        clicked = empty_state_card(
            "No jobs loaded",
            "Run an analysis on a repository to see job-level details here.",
            status="warning",
            icon="🔍",
            button_label="Run Analysis",
            button_key="job_analysis_run_analysis",
        )
        if clicked:
            st.session_state["_nav_idx2"] = 1
            st.rerun()
        return

    # ------------------------------------------------------------------
    # Build versioned dropdown labels: "JobName  v0.2" sorted descending
    # ------------------------------------------------------------------
    import re as _re

    def _ver_tuple(v):
        """Convert version string like '0.2' to tuple (0, 2) for sorting."""
        try:
            return tuple(int(x) for x in str(v).split("."))
        except Exception:
            return (0, 0)

    # Sort all_jobs: primary key = job_name asc, secondary key = version desc
    _sorted_jobs = sorted(
        all_jobs,
        key=lambda j: (
            j["job_data"].get("job_name", ""),
            tuple(-x for x in _ver_tuple(j["job_data"].get("job_version", "0.1"))),
        ),
    )

    # Build unique display labels — add version suffix when duplicates exist
    _name_counts = {}
    for j in _sorted_jobs:
        n = j["job_data"].get("job_name", "")
        _name_counts[n] = _name_counts.get(n, 0) + 1

    _job_labels = []
    _label_to_job = {}
    for j in _sorted_jobs:
        n = j["job_data"].get("job_name", "")
        v = j["job_data"].get("job_version", "")
        label = f"{n}  v{v}" if _name_counts.get(n, 1) > 1 else n
        # Deduplicate labels (edge case: same name + same version twice)
        if label in _label_to_job:
            label = f"{label} ({id(j)})"
        _job_labels.append(label)
        _label_to_job[label] = j

    # Resolve current session selection to a label
    _pending_job = st.session_state.pop("_job360_open_job", "")
    _prev = _pending_job or st.session_state.get("selected_job", "")
    _default_idx = 0
    for _i, _lbl in enumerate(_job_labels):
        if _lbl == _prev or _lbl.startswith(_prev + "  v") or _lbl.startswith(_prev):
            _default_idx = _i
            break

    # Resolve current label for header (before selectbox renders)
    _prev_label = st.session_state.get("selected_job", _job_labels[_default_idx] if _job_labels else "")
    _header_label = _prev_label if _prev_label in _label_to_job else (_job_labels[_default_idx] if _job_labels else "No job selected")
    page_header("🔍", "Job 360 Analysis", _header_label)

    sel_label = st.selectbox(
        "Select Job",
        _job_labels,
        index=_default_idx,
        key="selected_job",
    )

    job = _label_to_job.get(sel_label)
    sel_job = job["job_data"].get("job_name", sel_label) if job else sel_label

    repo_path = st.session_state.get("last_repo_path", "—")

    if not job:
        st.warning("Job not found.")
        return

    jd = job["job_data"]
    job_name = jd.get("job_name", "—")
    job_version = jd.get("job_version", "—")
    job_path = job.get("file_path") or (
        os.path.join(repo_path, job_name) if repo_path and repo_path != "—" else "—"
    )

    talend_version = jd.get("talend_version", "—")


    # ── Shared computed data (computed ONCE, reused across all tabs + export) ──
    _shared_key = f"_360_shared_{job_name}"
    if _shared_key not in st.session_state:
        _inv = build_source_target_inventory(jd)
        _sql_ops = extract_sql_operations(jd.get("components", []))
        _all_recs = generate_auto_fix_recommendations(all_jobs)
        _flow_steps = _build_flow_steps(jd)
        st.session_state[_shared_key] = {
            "inv": _inv,
            "sql_ops": _sql_ops,
            "all_recs": _all_recs,
            "flow_steps": _flow_steps,
        }
    _shared = st.session_state[_shared_key]
    _inv         = _shared["inv"]
    _sql_ops     = _shared["sql_ops"]
    _all_recs    = _shared["all_recs"]
    _flow_steps  = _shared["flow_steps"]

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'background:#fff;border:1px solid #e4e3dc;border-radius:14px;padding:10px 18px;margin-bottom:10px;">'
        f'<span style="font-size:14px;font-weight:700;color:#1a1a18;">Job Analysis 360</span>'
        f'<div style="display:flex;gap:10px;flex-wrap:wrap;">'
        f'<span style="background:#EEEDFE;color:#3C3489;font-size:12px;font-weight:600;padding:5px 14px;border-radius:20px;">Job Name: {job_name}</span>'
        f'<span style="background:#EEEDFE;color:#3C3489;font-size:12px;font-weight:600;padding:5px 14px;border-radius:20px;">Talend Version: {talend_version}</span>'
        f'<span style="background:#EEEDFE;color:#3C3489;font-size:12px;font-weight:600;padding:5px 14px;border-radius:20px;">Job Version: {job_version}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── Build 360 export content once per job (cached in session state) ────
    _export_key = f"_360_export_{job_name}"
    if _export_key not in st.session_state:
        # ── Build comprehensive 360 export content (all tabs) ─────────────────
        complexity = job.get("complexity", {})
        _exp_level = complexity.get("complexity", "—")
        _exp_score = complexity.get("score", "—")
        _exp_risk_factors = complexity.get("risk_factors", [])
        _exp_effort = EFFORT_HOURS["manual"] if _exp_level in ("HIGH", "CRITICAL") else EFFORT_HOURS["auto"]
        _exp_inv = _inv
        _exp_sources = [s.get("name", "") for s in _exp_inv.get("sources", []) if s.get("name")]
        _exp_targets = [t.get("name", "") for t in _exp_inv.get("targets", []) if t.get("name")]
        _exp_sql_ops = _sql_ops
        _exp_components = jd.get("components", [])
        _exp_flow_steps = _flow_steps

        # Functional rules
        _exp_func_rules = []
        for _c in _exp_components:
            _ctype = _c.get("component_type", "")
            _uid = _c.get("unique_name", _ctype)
            _params = component_parameters(_c)
            _rule_params = {
                k: v for k, v in _params.items()
                if v and any(tok in k.upper() for tok in ("QUERY", "CONDITION", "FILTER", "EXPRESSION", "JOIN", "TABLE"))
            }
            if _rule_params:
                for k, v in _rule_params.items():
                    _exp_func_rules.append(f"{_ctype} ({_uid}) — {k}: {str(v)[:300]}")

        # Dependencies (upstream/downstream)
        _exp_downstream = []
        for _c in _exp_components:
            if _c.get("component_type") != "tRunJob":
                continue
            _p = component_parameters(_c)
            _ch = normalize_name(
                _p.get("PROCESS") or _p.get("JOB_NAME") or _p.get("CHILD_JOB")
                or _p.get("PROCESS_NAME") or _p.get("SUBPROCESS")
            )
            if _ch:
                _exp_downstream.append(_ch)

        _exp_upstream = []
        for _j in all_jobs:
            _ojd = _j["job_data"]
            _oname = _ojd.get("job_name", "")
            if _oname == job_name:
                continue
            for _c in _ojd.get("components", []):
                if _c.get("component_type") != "tRunJob":
                    continue
                _p = component_parameters(_c)
                _ref = normalize_name(
                    _p.get("PROCESS") or _p.get("JOB_NAME") or _p.get("CHILD_JOB")
                    or _p.get("PROCESS_NAME") or _p.get("SUBPROCESS")
                )
                if _ref == job_name:
                    _exp_upstream.append(_oname)

        # Migration analysis
        _AUTO_COMP = {
            "tMap", "tFilterRow", "tSortRow", "tAggregateRow", "tJoin", "tUnite", "tDenormalize",
            "tNormalize", "tSampleRow", "tReplaceList", "tSetGlobalVar", "tLogRow", "tWarn",
            "tDie", "tFileInputDelimited", "tFileOutputDelimited", "tFileInputExcel", "tFileOutputExcel",
            "tDBInput", "tDBOutput", "tDBRow", "tDBCommit", "tDBClose",
            "tMSSqlInput", "tMSSqlOutput", "tMSSqlRow", "tOracleInput", "tOracleOutput",
            "tMysqlInput", "tMysqlOutput", "tPostgresqlInput", "tPostgresqlOutput",
            "tSnowflakeInput", "tSnowflakeOutput", "tBigQueryInput", "tBigQueryOutput",
            "tS3Get", "tS3Put", "tAzureBlobInput", "tAzureBlobOutput",
        }
        _MANUAL_COMP = {
            "tJava", "tJavaFlex", "tJavaRow", "tJavaIf", "tJavaInput",
            "tRunJob", "tPreJob", "tPostJob", "tParallelize",
            "tSendMail", "tFTPGet", "tFTPPut", "tSFTPGet", "tSFTPPut",
            "tWSDLInput", "tSOAPInput", "tRESTClient", "tRESTRequest",
        }
        _exp_auto_comps = [c for c in _exp_components if c.get("component_type", "") in _AUTO_COMP]
        _exp_manual_comps = [c for c in _exp_components if c.get("component_type", "") in _MANUAL_COMP]
        _exp_unknown_comps = [
            c for c in _exp_components
            if c.get("component_type", "") not in _AUTO_COMP and c.get("component_type", "") not in _MANUAL_COMP
        ]
        _exp_auto_pct = round(len(_exp_auto_comps) / max(len(_exp_components), 1) * 100)

        _VENDOR_FUNCS = {
            "NVL", "NVL2", "DECODE", "ROWNUM", "SYSDATE", "SYSTIMESTAMP",
            "ISNULL", "GETDATE", "GETUTCDATE", "NEWID", "CHARINDEX", "DATEPART", "DATEDIFF", "IIF",
            "IFNULL", "GROUP_CONCAT", "DATE_FORMAT", "STR_TO_DATE",
            "GENERATE_SERIES", "STRING_AGG", "ARRAY_AGG", "DATE_TRUNC", "TO_CHAR",
            "LISTAGG", "MEDIAN", "SAFE_CAST", "TIMESTAMP_TRUNC",
        }
        _exp_vendor_funcs = set()
        for _op in _exp_sql_ops:
            _su = str(_op.get("query", "")).upper()
            for _vf in _VENDOR_FUNCS:
                if re.search(r"\b" + re.escape(_vf) + r"\b", _su):
                    _exp_vendor_funcs.add(_vf)

        # Recommendations
        _exp_all_recs = _all_recs
        _exp_job_recs = [r for r in _exp_all_recs if r["job_name"] == job_name]
        _exp_auto_fixes = [r for r in _exp_job_recs if r["auto_fix"]]
        _exp_manual_fixes = [r for r in _exp_job_recs if not r["auto_fix"]]

        # Java logic components
        _exp_java_comps = [
            c for c in _exp_components
            if "java" in c.get("component_type", "").lower()
        ]

        # Use sel_job (live dropdown value) for file names so switching jobs
        # always produces a correctly-named file without Streamlit key collisions.
        st.session_state[_export_key] = {
            "level": _exp_level, "score": _exp_score, "risk_factors": _exp_risk_factors,
            "effort": _exp_effort, "sources": _exp_sources, "targets": _exp_targets,
            "sql_ops": _exp_sql_ops, "components": _exp_components, "flow_steps": _exp_flow_steps,
            "func_rules": _exp_func_rules, "upstream": _exp_upstream, "downstream": _exp_downstream,
            "auto_pct": _exp_auto_pct, "auto_comps": _exp_auto_comps, "manual_comps": _exp_manual_comps,
            "unknown_comps": _exp_unknown_comps, "vendor_funcs": _exp_vendor_funcs,
            "auto_fixes": _exp_auto_fixes, "manual_fixes": _exp_manual_fixes, "java_comps": _exp_java_comps,
        }
    _cached = st.session_state[_export_key]
    _exp_level = _cached["level"]; _exp_score = _cached["score"]; _exp_risk_factors = _cached["risk_factors"]
    _exp_effort = _cached["effort"]; _exp_sources = _cached["sources"]; _exp_targets = _cached["targets"]
    _exp_sql_ops = _cached["sql_ops"]; _exp_components = _cached["components"]; _exp_flow_steps = _cached["flow_steps"]
    _exp_func_rules = _cached["func_rules"]; _exp_upstream = _cached["upstream"]; _exp_downstream = _cached["downstream"]
    _exp_auto_pct = _cached["auto_pct"]; _exp_auto_comps = _cached["auto_comps"]; _exp_manual_comps = _cached["manual_comps"]
    _exp_unknown_comps = _cached["unknown_comps"]; _exp_vendor_funcs = _cached["vendor_funcs"]
    _exp_auto_fixes = _cached["auto_fixes"]; _exp_manual_fixes = _cached["manual_fixes"]; _exp_java_comps = _cached["java_comps"]

    # ── Job 360 hero KPI strip ────────────────────────────────────────────────
    _hero_cx = job.get("complexity", {})
    _hero_level = _hero_cx.get("complexity", "LOW")
    _hero_score = _hero_cx.get("score", 0)
    _hero_effort = EFFORT_HOURS["manual"] if _hero_level in ("HIGH", "CRITICAL") else EFFORT_HOURS["auto"]
    _hero_cloud = "Not Ready" if _hero_effort == EFFORT_HOURS["manual"] else "Ready"
    _hero_recs = [r for r in _all_recs if r["job_name"] == job_name]
    _hero_auto_fixes = [r for r in _hero_recs if r.get("auto_fix")]
    _hero_total_comps = len(jd.get("components", []))
    _hero_risk_items = [r for r in job.get("enterprise_risk_report", []) if (r.get("risk") or "").upper() in ("HIGH", "CRITICAL")]
    render_kpi_row([
        {"label": "Complexity", "value": _hero_level, "caption": f"Score: {_hero_score}", "color": "#15803d" if _hero_level == "LOW" else "#b45309" if _hero_level == "MEDIUM" else "#be123c"},
        {"label": "Cloud Readiness", "value": _hero_cloud, "caption": f"Est. {_hero_effort}h effort", "color": "#15803d" if _hero_cloud == "Ready" else "#be123c"},
        {"label": "Components", "value": _hero_total_comps, "caption": "In this job", "color": "#1d4ed8"},
        {"label": "High/Critical Risks", "value": len(_hero_risk_items), "caption": "Needs attention" if _hero_risk_items else "All clear", "color": "#be123c" if _hero_risk_items else "#15803d"},
    ])
    _default_tab = st.session_state.pop("_job360_active_tab", 0)

    # ── Phase 2A: Categorised Job 360 Navigation ─────────────────────────────
    _cat_labels = JOB360_CATEGORY_LABELS
    _pending_category = st.session_state.pop("_job360_open_category", "")
    if _pending_category in _cat_labels:
        st.session_state["job360_cat_nav"] = _pending_category
    _cat_sel = st.radio(
        "Category", _cat_labels, horizontal=True,
        label_visibility="collapsed", key="job360_cat_nav",
    )

    if _cat_sel == "Overview":
        _ov_dash, _ov_summary, _ov_func, _ov_exec, _ov_ai = st.tabs(["Dashboard", "Summary", "Functional", "Executive Summary", "AI Summary"])
        with _ov_dash:
            # Dashboard: uses existing Job360 metadata only (_inv, _sql_ops, _cached, job, jd).
            _dsh_cx = job.get("complexity", {})
            _dsh_level = _dsh_cx.get("complexity") or _dsh_cx.get("level") or _cached.get("level", "LOW")
            _dsh_score = _dsh_cx.get("score", _cached.get("score", 0))
            _dsh_cloud = job.get("cloud_readiness", {})
            _dsh_rag = _cloud_rag(_dsh_cloud)
            _dsh_comps = jd.get("components", [])
            _dsh_srcs = _inv.get("sources", [])
            _dsh_tgts = _inv.get("targets", [])
            _dsh_src_names = [s.get("qualified_name") or s.get("name") for s in _dsh_srcs if s.get("qualified_name") or s.get("name")]
            _dsh_tgt_names = [t.get("qualified_name") or t.get("name") for t in _dsh_tgts if t.get("qualified_name") or t.get("name")]
            _dsh_tmaps = [c for c in _dsh_comps if c.get("component_type", "") == "tMap"]
            _dsh_mapping_count = len(jd.get("column_mappings", []) or []) or len(_dsh_tmaps)
            _dsh_sql = _sql_ops
            _dsh_java = [c for c in _dsh_comps if c.get("component_type", "") in {"tJava", "tJavaRow", "tJavaFlex"}]
            _dsh_deps = job.get("dependencies", {})
            _dsh_dependency_count = sum(len(_dsh_deps.get(k, []) or []) for k in ("parent_jobs", "child_jobs", "joblets", "routines", "contexts", "metadata_connections"))
            _dsh_risks = [r for r in job.get("enterprise_risk_report", []) if (r.get("risk") or r.get("severity") or "").upper() in ("HIGH", "CRITICAL")]
            _dsh_risk_factors = _dsh_cx.get("risk_factors", []) or _cached.get("risk_factors", [])
            _dsh_unknown = _cached.get("unknown_comps", [])
            _dsh_manual = _cached.get("manual_comps", [])
            _dsh_effort = _cached.get("effort", EFFORT_HOURS["manual"] if _dsh_level in ("HIGH", "CRITICAL") else EFFORT_HOURS["auto"])
            try:
                _dsh_readiness_score = int(float(_dsh_cloud.get("cloud_readiness_score") or _dsh_cloud.get("score") or (85 if _dsh_rag == "GREEN" else 55 if _dsh_rag == "AMBER" else 25)))
            except (TypeError, ValueError):
                _dsh_readiness_score = 85 if _dsh_rag == "GREEN" else 55 if _dsh_rag == "AMBER" else 25
            _dsh_validation_score = max(0, 100 - len(_dsh_risks) * 15 - len(_dsh_manual) * 2)
            _dsh_risk_score = min(100, len(_dsh_risks) * 20 + len(_dsh_risk_factors) * 10 + len(_dsh_java) * 8 + len(_dsh_unknown) * 6)
            _dsh_complex_java = len([c for c in _dsh_java if c.get("component_type") == "tJavaFlex"]) or (len(_dsh_java) if _dsh_level in ("HIGH", "CRITICAL") else 0)
            _dsh_unsupported_count = len(_dsh_unknown) + len([r for r in _hero_recs if "unsupported" in str(r.get("category", "")).lower() or "unsupported" in str(r.get("issue", "")).lower()])
            _dsh_transformations = sorted({c.get("component_type", "") for c in _dsh_comps if re.search(r"Map|Filter|Aggregate|Join|Sort|Normalize|Denormalize", c.get("component_type", ""), re.I)})
            _dsh_recommendations = [
                r.get("fix") or r.get("recommendation") or r.get("issue")
                for r in _hero_recs[:5]
                if r.get("fix") or r.get("recommendation") or r.get("issue")
            ] or [
                "Validate source-to-target counts after migration.",
                "Review Java and unsupported components before cutover.",
                "Run regression and reconciliation tests from the Testing tab.",
            ]

            st.markdown("#### Dashboard")
            render_kpi_row([
                {"label": "Job Name", "value": job_name, "caption": f"v{job_version}", "color": "#1d4ed8"},
                {"label": "Source Count", "value": len(_dsh_srcs), "caption": "detected sources", "color": "#0f766e"},
                {"label": "Target Count", "value": len(_dsh_tgts), "caption": "detected targets", "color": "#7c3aed"},
                {"label": "Component Count", "value": len(_dsh_comps), "caption": "parsed metadata", "color": "#b45309"},
            ])
            render_kpi_row([
                {"label": "Mapping Count", "value": _dsh_mapping_count, "caption": "column mappings / tMaps", "color": "#0369a1"},
                {"label": "SQL Objects", "value": len(_dsh_sql), "caption": "cached SQL ops", "color": "#0e7490"},
                {"label": "Java Objects", "value": len(_dsh_java), "caption": "tJava family", "color": "#7c3aed"},
                {"label": "Dependency Count", "value": _dsh_dependency_count, "caption": "jobs, routines, contexts", "color": "#374151"},
            ])
            render_kpi_row([
                {"label": "Complexity Score", "value": _dsh_score, "caption": _dsh_level, "color": "#be123c" if _dsh_level in ("HIGH", "CRITICAL") else "#15803d"},
                {"label": "Migration Readiness", "value": _dsh_readiness_score, "caption": _dsh_rag, "color": "#15803d" if _dsh_rag == "GREEN" else "#b45309" if _dsh_rag == "AMBER" else "#be123c"},
                {"label": "Validation Score", "value": _dsh_validation_score, "caption": "derived from risks", "color": "#0f766e" if _dsh_validation_score >= 70 else "#b45309"},
                {"label": "Risk Score", "value": _dsh_risk_score, "caption": "higher = more risk", "color": "#be123c" if _dsh_risk_score >= 50 else "#15803d"},
            ])
            render_kpi_row([
                {"label": "Estimated Effort", "value": f"{_dsh_effort}h", "caption": "migration effort", "color": "#6d28d9"},
            ])

            st.divider()
            st.markdown("#### Quick Insights")
            _insight_rows = [
                {"Insight": "Sources Detected", "Value": len(_dsh_srcs), "Details": ", ".join(_dsh_src_names[:6]) or "None detected"},
                {"Insight": "Targets Detected", "Value": len(_dsh_tgts), "Details": ", ".join(_dsh_tgt_names[:6]) or "None detected"},
                {"Insight": "Mappings Extracted", "Value": _dsh_mapping_count, "Details": "Column mappings available" if jd.get("column_mappings") else "Using tMap count as mapping proxy"},
                {"Insight": "Unsupported Components", "Value": _dsh_unsupported_count, "Details": ", ".join(c.get("component_type", "") for c in _dsh_unknown[:6]) or "None flagged in cached metadata"},
                {"Insight": "Complex Java Logic", "Value": _dsh_complex_java, "Details": ", ".join(c.get("unique_name") or c.get("component_type", "") for c in _dsh_java[:6]) or "None detected"},
                {"Insight": "Migration Risks", "Value": len(_dsh_risks) + len(_dsh_risk_factors), "Details": ", ".join(map(str, _dsh_risk_factors[:6])) or "No explicit risk factors"},
            ]
            st.dataframe(pd.DataFrame(_insight_rows), use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("#### AI Summary")
            _purpose_text = (
                f"{job_name} reads from {', '.join(_dsh_src_names[:4])} and delivers data to {', '.join(_dsh_tgt_names[:4])}."
                if _dsh_src_names and _dsh_tgt_names else
                f"{job_name} processes detected source data for downstream use."
                if _dsh_src_names else
                f"{job_name} produces target outputs from internal or upstream processing."
                if _dsh_tgt_names else
                f"{job_name} performs internal orchestration or utility processing."
            )
            _summary_rows = [
                {"Area": "Job Purpose", "Summary": _purpose_text},
                {"Area": "Source Systems", "Summary": ", ".join(_dsh_src_names[:8]) or "None detected"},
                {"Area": "Target Systems", "Summary": ", ".join(_dsh_tgt_names[:8]) or "None detected"},
                {"Area": "Key Transformations", "Summary": ", ".join(_dsh_transformations[:8]) or "No explicit transformation components detected"},
                {"Area": "Risks", "Summary": ", ".join(map(str, _dsh_risk_factors[:6])) or ("High/critical risks present" if _dsh_risks else "No major risks detected")},
                {"Area": "Recommendations", "Summary": " ".join(f"- {r}" for r in _dsh_recommendations)},
            ]
            st.dataframe(pd.DataFrame(_summary_rows), use_container_width=True, hide_index=True)
        with _ov_summary:
            st.markdown("#### Summary")
            render_kpi_row([
                {"label": "Complexity", "value": _hero_level, "caption": f"Score: {_hero_score}", "color": "#15803d" if _hero_level == "LOW" else "#b45309" if _hero_level == "MEDIUM" else "#be123c"},
                {"label": "Cloud Readiness", "value": _hero_cloud, "caption": f"Est. {_hero_effort}h effort", "color": "#15803d" if _hero_cloud == "Ready" else "#be123c"},
                {"label": "Components", "value": _hero_total_comps, "caption": "In this job", "color": "#1d4ed8"},
                {"label": "High/Critical Risks", "value": len(_hero_risk_items), "caption": "Needs attention" if _hero_risk_items else "All clear", "color": "#be123c" if _hero_risk_items else "#15803d"},
            ])
            st.markdown(f"**Job:** `{job_name}`")
            st.markdown(f"**Version:** `{job_version}`")
            st.markdown(f"**Purpose:** {purpose if 'purpose' in locals() else 'Repository job analysis summary.'}")

        with _ov_ai:
            st.markdown("#### AI Summary")
            _ai_sum_key = f"_ov_ai_summary_{job_name}"
            if _ai_sum_key not in st.session_state:
                try:
                    from app.tiap.exec_summary.exec_summary import build_executive_summary
                    _ai_sum_data = build_executive_summary(jd)
                    st.session_state[_ai_sum_key] = _ai_sum_data
                except Exception:
                    st.session_state[_ai_sum_key] = {"business_summary": "AI summary unavailable.", "technical_summary": ""}
            _ai_sum = st.session_state[_ai_sum_key]
            with st.expander("Business Summary", expanded=True):
                st.markdown(_ai_sum.get("business_summary","—"))
            with st.expander("Technical Summary", expanded=False):
                st.markdown(_ai_sum.get("technical_summary","—"))
        with _ov_exec:
            complexity = job.get("complexity", {})
            level = complexity.get("complexity", "LOW")
            score = complexity.get("score", "—")
            risk_factors = complexity.get("risk_factors", [])
            effort_hours = EFFORT_HOURS["manual"] if level in ("HIGH", "CRITICAL") else EFFORT_HOURS["auto"]

            all_recs = _all_recs
            job_recs = [r for r in all_recs if r["job_name"] == job_name]
            auto_fixes = [r for r in job_recs if r["auto_fix"]]
            manual_fixes = [r for r in job_recs if not r["auto_fix"]]

            inv = _inv
            sources = inv.get("source_names", [])
            targets = inv.get("target_names", [])
            sql_ops = inv.get("sql_operations", [])
            sources_full = inv.get("sources", [])
            targets_full = inv.get("targets", [])

            joblets = []
            seen_joblets = set()
            child_jobs = []
            routine_usage: dict[str, int] = {}
            for c in jd.get("components", []):
                ctype = c.get("component_type", "")
                if ctype.lower().startswith("tjoblet") or ctype == "tJoblet":
                    params = component_parameters(c)
                    jn = normalize_name(params.get("JOBLET") or params.get("PROCESS") or c.get("unique_name") or ctype)
                    if jn and jn not in seen_joblets:
                        seen_joblets.add(jn)
                        joblets.append(jn)
                if ctype == "tRunJob":
                    params = component_parameters(c)
                    cj = normalize_name(
                        params.get("PROCESS") or params.get("JOB_NAME") or params.get("CHILD_JOB")
                        or params.get("PROCESS_NAME") or params.get("SUBPROCESS")
                    )
                    if cj:
                        child_jobs.append(cj)
                for value in (c.get("parameters") or {}).values():
                    for rname in re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", str(value)):
                        routine_usage[rname] = routine_usage.get(rname, 0) + 1

            if sources and targets:
                purpose = (
                    f"This job reads data from {', '.join(sources)} "
                    f"and delivers it to {', '.join(targets)}."
                )
            elif sources:
                purpose = f"This job reads and processes data from {', '.join(sources)}."
            elif targets:
                purpose = f"This job produces output data for {', '.join(targets)}."
            else:
                purpose = "This job performs internal processing with no clearly identified external sources or targets."
            if sql_ops:
                purpose += f" It also performs {len(sql_ops)} direct database operation(s) as part of its processing."

            level_colors = {
                "LOW": "#15803d", "MEDIUM": "#b45309", "HIGH": "#be123c", "CRITICAL": "#be123c",
            }
            level_bg = {
                "LOW": "#f0fdf4", "MEDIUM": "#fffbeb", "HIGH": "#fff1f2", "CRITICAL": "#fff1f2",
            }
            cloud_readiness_colors = {
                "Ready": ("#f0fdf4", "#15803d"),
                "Not Ready": ("#fff1f2", "#be123c"),
            }

            st.markdown(
                """
                <style>
                .tma-header{background:#fff;border:1px solid #e4e3dc;border-radius:14px;padding:16px 22px;margin-bottom:14px;display:flex;align-items:flex-start;gap:18px;}
                .tma-header-icon{width:48px;height:48px;background:#EEEDFE;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;color:#3C3489;flex-shrink:0;}
                .tma-header h2{font-size:20px;font-weight:600;color:#1a1a18;margin-bottom:6px;}
                .tma-header p{font-size:13px;color:#6b6b66;line-height:1.7;margin:0;}
                .tma-header code{background:#f0eee8;padding:2px 7px;border-radius:5px;font-size:12px;color:#3C3489;}
                .tma-sec-label{font-size:11px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:#8a8a85;margin:14px 0 8px;}
                .tma-flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));border:1px solid #e4e3dc;border-radius:12px;overflow:hidden;margin-bottom:6px;}
                .tma-fstep{background:#fff;padding:12px 14px;border-right:1px solid #e4e3dc;}
                .tma-fstep:last-child{border-right:none;}
                .tma-fstep .num{font-size:10px;font-weight:600;color:#b0aea8;letter-spacing:.05em;margin-bottom:6px;}
                .tma-fstep .sicon{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:6px;background:#EEEDFE;color:#534AB7;}
                .tma-fstep .ftitle{font-size:12px;font-weight:600;color:#1a1a18;margin-bottom:4px;}
                .tma-fstep .fdet{font-size:11px;color:#6b6b66;line-height:1.5;}
                .tma-highlight{background:#fff;border:1px solid #e4e3dc;border-left:4px solid #854F0B;border-radius:0 12px 12px 0;padding:10px 16px;margin-bottom:10px;}
                .tma-highlight .htitle{font-size:13px;font-weight:600;color:#1a1a18;margin-bottom:4px;}
                .tma-highlight .hbody{font-size:12px;color:#5a5a56;}
                .tma-tag-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;}
                .tma-tag{font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;background:#FAEEDA;color:#633806;}
                .tma-badge-row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px;}
                .tma-badge{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;padding:4px 11px;border-radius:20px;background:#EEEDFE;color:#3C3489;}
                .tma-cgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:6px;}
                .tma-card{background:#fff;border:1px solid #e4e3dc;border-radius:12px;padding:12px;}
                .tma-card .ci{font-size:12px;font-weight:600;color:#8a8a85;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;}
                .tma-card .cv{font-size:24px;font-weight:900;color:#3C3489;margin-bottom:4px;}
                .tma-card .cs{font-size:11px;color:#6b6b66;}
                .st-key-business_overview,
                .st-key-business_overview *{box-sizing:border-box;min-width:0;}
                .st-key-business_overview{margin:4px 0 10px;}
                .st-key-business_overview [data-testid="stCaptionContainer"]{margin-bottom:8px;}
                .st-key-business_overview div[data-testid="stHorizontalBlock"]{gap:10px!important;align-items:stretch;}
                .bo-card{background:#fff;border:1px solid #e4e3dc;border-radius:10px;padding:12px 14px;min-height:150px;height:100%;overflow:hidden;margin:2px 0 10px;}
                .bo-card-title,.bo-card .bf-card-title{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:0;line-height:1.3;margin-bottom:8px;overflow-wrap:anywhere;word-break:break-word;}
                .bo-card-body,.bo-card .bf-card-body{font-size:13px;color:#2d2d2a;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;}
                .bo-card-body ul,.bo-card .bf-card-body ul{margin:0;padding-left:18px;}
                .bo-card-body li,.bo-card .bf-card-body li{margin-bottom:3px;overflow-wrap:anywhere;word-break:break-word;}
                .tma-compare-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;}
                .tma-cmp{background:#fff;border:1px solid #e4e3dc;border-radius:12px;padding:12px;}
                .tma-cmp.preferred{border:2px solid #378ADD;}
                .tma-cmp-title{font-size:13px;font-weight:600;color:#1a1a18;margin-bottom:8px;}
                .tma-cmp ul{list-style:none;padding:0;margin:0;}
                .tma-cmp li{font-size:12px;color:#5a5a56;line-height:1.6;padding:3px 0 3px 16px;position:relative;}
                .tma-cmp li::before{content:'';position:absolute;left:4px;top:9px;width:5px;height:5px;border-radius:50%;background:#b0aea8;}
                .tma-cmp.preferred li::before{background:#378ADD;}
                .tma-pitch{background:#fff;border:1px solid #e4e3dc;border-left:4px solid #534AB7;border-radius:0 12px 12px 0;padding:12px 18px;}
                .tma-pitch p{font-size:13px;color:#3a3a36;line-height:1.7;font-style:italic;margin:0;}
                div[data-testid="stVerticalBlock"] > div{gap:0.4rem;}
                div.block-container{padding-top:1.2rem;}
                </style>
                """,
                unsafe_allow_html=True,
            )

            # ── Business Overview ─────────────────────────────────────────────────
            st.markdown("---")
            st.markdown("#### 📋 Business Overview")
            st.caption("Key metrics for this job at a glance.")
            _bo_sources = _inv.get("source_names", [])
            _bo_targets = _inv.get("target_names", [])
            _bo_level = job.get("complexity", {}).get("complexity", "LOW")
            _bo_c1, _bo_c2, _bo_c3, _bo_c4 = st.columns(4)
            with _bo_c1:
                st.markdown(
                    '<div class="tma-card"><div class="ci">Data Sources</div>'
                    f'<div class="cv">{len(_bo_sources)}</div>'
                    '<div class="cs">See details below</div></div>',
                    unsafe_allow_html=True,
                )
            with _bo_c2:
                st.markdown(
                    '<div class="tma-card"><div class="ci">Data Targets</div>'
                    f'<div class="cv">{len(_bo_targets)}</div>'
                    '<div class="cs">See details below</div></div>',
                    unsafe_allow_html=True,
                )
            with _bo_c3:
                st.markdown(
                    '<div class="tma-card"><div class="ci">SQL Operations</div>'
                    f'<div class="cv">{len(sql_ops)}</div>'
                    '<div class="cs">Direct DB operations</div></div>',
                    unsafe_allow_html=True,
                )
            with _bo_c4:
                st.markdown(
                    '<div class="tma-card"><div class="ci">Complexity</div>'
                    f'<div class="cv">{_bo_level}</div>'
                    '<div class="cs">Migration classification</div></div>',
                    unsafe_allow_html=True,
                )

            with st.expander("🔍 View data sources & targets"):
                _bo_dc1, _bo_dc2 = st.columns(2)
                with _bo_dc1:
                    st.markdown("**Data Sources**")
                    if _bo_sources:
                        for _s in _bo_sources:
                            st.markdown(f"- {_s}")
                    else:
                        st.caption("None detected")
                with _bo_dc2:
                    st.markdown("**Data Targets**")
                    if _bo_targets:
                        for _t in _bo_targets:
                            st.markdown(f"- {_t}")
                    else:
                        st.caption("None detected")

            if sql_ops:
                with st.expander(f"🗃️ View SQL operations ({len(sql_ops)})"):
                    for _op in sql_ops:
                        st.markdown(f"**{_op.get('component', 'SQL component')}** &nbsp;·&nbsp; {_op.get('db_type', 'unknown DB')}")
                        st.code(_op.get("query", "") or "—", language="sql")

            st.markdown("")

            # ── Executive Summary ────────────────────────────────────────────────
            st.markdown("## Executive Summary")
            _cx_color = level_colors.get(level, "#1a1a18")
            _cx_bg = level_bg.get(level, "#f5f5f0")
            _cloud_readiness = "Not Ready" if effort_hours == EFFORT_HOURS["manual"] else "Ready"
            _cr_bg, _cr_fg = cloud_readiness_colors.get(_cloud_readiness, ("#EEF2FF", "#3730A3"))
            component_count = len(jd.get("components", []))
            dependency_count = len(child_jobs) + len(joblets) + len(routine_usage)
            custom_code_count = sum(
                1 for c in jd.get("components", [])
                if "java" in str(c.get("component_type", "")).lower()
            )
            detected_unsupported = [
                r.get("component", "Unsupported component")
                for r in job.get("enterprise_risk_report", [])
                if r.get("component")
            ]
            unsupported = list(dict.fromkeys([
                "Custom Java",
                "External Scripts",
                "Legacy Components",
                "Dependencies",
                *detected_unsupported,
            ]))
            local_file_count = sum(
                1 for c in jd.get("components", [])
                if "file" in str(c.get("component_type", "")).lower()
            )
            complexity_details = {
                "components": {
                    "Components": component_count,
                    "SQL Logic": len(sql_ops),
                    "Dependencies": dependency_count,
                    "Custom Code": custom_code_count,
                    "Migration Risk": len(risk_factors),
                },
                "total_score": score,
                "notes": "Derived from parsed components, SQL operations, dependencies, custom code, and risk factors.",
            }
            risk_details = {
                "unsupported_components": unsupported,
                "risk_score": score,
                "risk_rating": level,
                "notes": "Uses the current complexity level and enterprise risk findings for this job.",
            }
            effort_details = {
                "hours": {
                    "Analysis Hours": 2,
                    "SQL Conversion": len(sql_ops) * 2,
                    "Component Migration": max(1, component_count // 5),
                    "Testing": 4 if effort_hours == EFFORT_HOURS["manual"] else 1,
                    "Validation": 2,
                },
                "total_hours": effort_hours,
                "notes": "Total hours use the configured migration effort setting for this complexity class.",
            }
            cloud_details = {
                "positive": ["Standard Components", "Metadata Driven"],
                "negative": ["Custom Java", "Local Files", "Unsupported Components"],
                "readiness_score": _cloud_readiness,
                "notes": f"{len(auto_fixes)} auto-fix(es) and {len(manual_fixes)} manual fix(es) are currently identified.",
            }
            st.markdown(f'<div class="tma-pitch"><p>{purpose}</p></div>', unsafe_allow_html=True)

            _biz_key = f"job_biz_summary_{job_name}"
            _biz_c1, _biz_c2 = st.columns([1, 3])
            _biz_use_ai = _biz_c1.checkbox("🤖 Use AI (Ollama)", value=False, key=f"biz_use_ai_{job_name}")
            if _biz_c2.button("✨ Explain in business terms", key=f"btn_biz_{job_name}"):
                _biz_prompt = (
                    "You are a business analyst explaining a data integration job to a non-technical stakeholder.\n"
                    "Rules: plain business language only, no code or technical component names, describe WHAT the "
                    "job accomplishes and WHY it matters (not how), one short paragraph under 100 words, no bullets.\n\n"
                    f"Job name: {job_name}\n"
                    f"Technical summary: {purpose}\n"
                    f"Data sources: {', '.join(sources) or 'none detected'}\n"
                    f"Data destinations: {', '.join(targets) or 'none detected'}\n"
                    f"SQL operations: {len(sql_ops)}\n"
                    f"Complexity: {level}\n\n"
                    "Write a simple, one-paragraph business explanation of this job."
                )
                with st.spinner("Writing business summary…"):
                    st.session_state[_biz_key] = ask_ollama(_biz_prompt, use_ollama=_biz_use_ai)

            _biz_summary = st.session_state.get(_biz_key)
            if _biz_summary:
                st.markdown(
                    f'<div class="tma-pitch" style="border-left-color:#3C3489;"><p>🧠 {_biz_summary}</p></div>',
                    unsafe_allow_html=True,
                )

            badge_cols = st.columns(4)
            with badge_cols[0]:
                render_kpi_badge("Complexity", level, details=complexity_details, key=f"{job_name}_complexity_badge")
            with badge_cols[1]:
                render_kpi_badge("Migration Risk", level, details=risk_details, key=f"{job_name}_risk_badge")
            with badge_cols[2]:
                render_kpi_badge("Migration Effort", f"{effort_hours}h", details=effort_details, key=f"{job_name}_effort_badge")
            with badge_cols[3]:
                render_kpi_badge("Cloud Readiness", _cloud_readiness, details=cloud_details, key=f"{job_name}_cloud_badge")

            # ── Header card ──────────────────────────────────────────────────────
            st.markdown(
                f"""
                <div class="tma-header">
                  <div class="tma-header-icon">🔍</div>
                  <div>
                    <h2>{job_name}</h2>
                    <p>
                      Path: <code>{job_path}</code> &nbsp;·&nbsp;
                      Repository: <code>{repo_path}</code> &nbsp;·&nbsp;
                      Version: <code>{job_version}</code> &nbsp;·&nbsp;
                      Talend: <code>{talend_version}</code> &nbsp;·&nbsp;
                      Complexity Status: <code>{level}</code>
                    </p>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ── Job versions ─────────────────────────────────────────────────────
            all_versions = [j for j in all_jobs if j["job_data"].get("job_name") == job_name]
            if len(all_versions) > 1:
                st.markdown('<div class="tma-sec-label">Job versions found in repository</div>', unsafe_allow_html=True)
                for j in sorted(all_versions, key=lambda x: x["job_data"].get("job_version", "0.1")):
                    v_jd = j["job_data"]
                    st.markdown(f"- Version `{v_jd.get('job_version', '—')}` — {j.get('file_path', '—')}")

            # ── Job flow ─────────────────────────────────────────────────────────
            st.markdown('<div class="tma-sec-label">How this job works — step by step</div>', unsafe_allow_html=True)

            steps = _flow_steps
            shown_steps = steps[:8]

            flow_html = '<div class="tma-flow">'
            for i, (icon, title, detail) in enumerate(shown_steps, start=1):
                flow_html += (
                    f'<div class="tma-fstep"><div class="num">STEP {i:02d}</div>'
                    f'<div class="sicon">{icon}</div>'
                    f'<div class="ftitle">{title}</div>'
                    f'<div class="fdet">{detail}</div></div>'
                )
            if len(steps) > len(shown_steps):
                flow_html += (
                    f'<div class="tma-fstep"><div class="num">+{len(steps) - len(shown_steps)} MORE</div>'
                    f'<div class="sicon">➕</div>'
                    f'<div class="ftitle">More steps</div>'
                    f'<div class="fdet">See Flowcharts tab for the full sequence</div></div>'
                )
            flow_html += '</div>'
            st.markdown(flow_html, unsafe_allow_html=True)

            # ── Complexity & risk highlight ──────────────────────────────────────
            st.markdown('<div class="tma-sec-label">Complexity &amp; migration risk</div>', unsafe_allow_html=True)
            tags_html = "".join(f'<span class="tma-tag">{rf}</span>' for rf in risk_factors)
            st.markdown(
                f"""
                <div class="tma-highlight">
                  <div class="htitle">Complexity Status: {level} &nbsp;·&nbsp; Migration Risk: {level}</div>
                  <div class="hbody">Estimated migration effort: {effort_hours}h
                    ({'Manual review required' if effort_hours == EFFORT_HOURS["manual"] else 'Auto-migratable'})</div>
                  <div class="tma-tag-row">{tags_html if tags_html else '<span class="tma-tag">No risk factors detected</span>'}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ── Sources & targets badges ────────────────────────────────────────
            st.markdown('<div class="tma-sec-label">Sources &amp; targets identified</div>', unsafe_allow_html=True)
            badges_html = '<div class="tma-badge-row">'
            for s in sources_full:
                badges_html += f'<span class="tma-badge">📥 {s.get("name","—")} <span style="font-weight:400;opacity:.7">{s.get("component","")}</span></span>'
            for t in targets_full:
                badges_html += f'<span class="tma-badge">📤 {t.get("name","—")} <span style="font-weight:400;opacity:.7">{t.get("component","")}</span></span>'
            if not sources_full and not targets_full:
                badges_html += '<span class="tma-badge">None detected</span>'
            badges_html += '</div>'
            st.markdown(badges_html, unsafe_allow_html=True)

            # ── Auto vs manual compare ──────────────────────────────────────────
            st.markdown('<div class="tma-sec-label">Recommendations — auto vs manual fixes</div>', unsafe_allow_html=True)
            auto_li = "".join(f"<li>{r['issue']} — {r['fix']}</li>" for r in auto_fixes) or "<li>None</li>"
            manual_li = "".join(f"<li>{r['issue']} — {r['fix']}</li>" for r in manual_fixes) or "<li>None</li>"
            st.markdown(
                f"""
                <div class="tma-compare-row">
                  <div class="tma-cmp preferred">
                    <div class="tma-cmp-title">✅ Auto Fixes</div>
                    <ul>{auto_li}</ul>
                  </div>
                  <div class="tma-cmp">
                    <div class="tma-cmp-title">⚠️ Manual Fixes</div>
                    <ul>{manual_li}</ul>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("#### Components")
            counts: dict[str, int] = {}
            for c in jd.get("components", []):
                ct = c.get("component_type", "Unknown")
                counts[ct] = counts.get(ct, 0) + 1
            if counts:
                for ct, cnt in sorted(counts.items(), key=lambda x: -x[1]):
                    st.markdown(f"- {ct}: {cnt}")
            else:
                st.markdown("- None")

            # ── Tabs: Child Jobs / Joblets / Routines / Metadata ─────────────────────
            tab_child, tab_joblets, tab_routines, tab_metadata = st.tabs(
                ["👶 Child Jobs", "🧩 Joblets", "📦 Routines", "🗂️ Metadata"]
            )

            with tab_child:
                st.markdown("#### Child Jobs")
                child_jobs = []
                for c in jd.get("components", []):
                    if c.get("component_type") != "tRunJob":
                        continue
                    params = component_parameters(c)
                    child = (
                        params.get("PROCESS")
                        or params.get("JOB_NAME")
                        or params.get("CHILD_JOB")
                        or params.get("PROCESS_NAME")
                        or params.get("SUBPROCESS")
                    )
                    child = normalize_name(child)
                    if child:
                        child_jobs.append(child)

                if child_jobs:
                    for cj in child_jobs:
                        st.markdown(f"- {cj}")
                else:
                    st.markdown("- None")

            with tab_joblets:
                st.markdown("#### Joblets")
                joblets = []
                seen_joblets = set()
                for c in jd.get("components", []):
                    ctype = c.get("component_type", "")
                    if ctype.lower().startswith("tjoblet") or ctype == "tJoblet":
                        params = component_parameters(c)
                        joblet_name = params.get("JOBLET") or params.get("PROCESS") or c.get("unique_name") or ctype
                        joblet_name = normalize_name(joblet_name)
                        if joblet_name and joblet_name not in seen_joblets:
                            seen_joblets.add(joblet_name)
                            joblets.append(joblet_name)

                if joblets:
                    for jn in joblets:
                        st.markdown(f"- **{jn}** — Reusable shared logic invoked by this job as part of its processing.")
                else:
                    st.markdown("- None")

            with tab_routines:
                st.markdown("#### Routines")
                routine_usage: dict[str, int] = {}
                for c in jd.get("components", []):
                    for value in (c.get("parameters") or {}).values():
                        for name in re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", str(value)):
                            routine_usage[name] = routine_usage.get(name, 0) + 1

                if routine_usage:
                    for name, count in sorted(routine_usage.items(), key=lambda x: -x[1]):
                        st.markdown(f"- {name}: used {count} time(s)")
                else:
                    st.markdown("- None")

            with tab_metadata:
                st.markdown("#### Metadata")
                # Collect metadata references from component parameter values
                metadata_refs: dict[str, list[str]] = {}
                meta_pattern = re.compile(
                    r"(?:metadata|repository)[/\\]([A-Za-z0-9_\-\.]+)", re.IGNORECASE
                )
                for c in jd.get("components", []):
                    ctype = c.get("component_type", "Unknown")
                    uid = c.get("unique_name", ctype)
                    params = component_parameters(c)
                    refs_found = set()
                    for value in params.values():
                        for match in meta_pattern.findall(str(value)):
                            name = normalize_name(match)
                            if name:
                                refs_found.add(name)
                        # Also catch schema/column param keys that look like metadata
                        for key in params:
                            if any(k in key.upper() for k in ("SCHEMA", "TABLE", "DBNAME", "FILENAME", "FILE_NAME")):
                                val = normalize_name(params[key])
                                if val and len(val) > 1:
                                    refs_found.add(f"{key}: {val}")
                    if refs_found:
                        metadata_refs[f"{ctype} ({uid})"] = sorted(refs_found)

                # Also surface context variables as metadata
                contexts = jd.get("contexts", [])
                context_vars = [
                    c for c in contexts
                    if isinstance(c, dict) and c.get("name")
                ]

                if metadata_refs:
                    st.markdown("**Repository / Schema References**")
                    for comp_label, refs in sorted(metadata_refs.items()):
                        st.markdown(f"**{comp_label}**")
                        for ref in refs:
                            st.markdown(f"  - {ref}")
                else:
                    st.markdown("**Repository / Schema References**")
                    st.markdown("- None")

                st.markdown("**Context Variables**")
                if context_vars:
                    for cv in context_vars:
                        name = cv.get("name", "—")
                        value = cv.get("value", "—")
                        st.markdown(f"- `{name}`: {value}")
                else:
                    st.markdown("- None")

            # ── SQL ───────────────────────────────────────────────────────────────────
            st.markdown("#### SQL")
            sql_ops = _sql_ops
            tables: set[str] = set()
            table_pattern = re.compile(
                r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([A-Za-z0-9_\.\"]+)", re.IGNORECASE
            )

            if sql_ops:
                for op in sql_ops:
                    query = op.get("query") or ""
                    st.markdown(f"- **{op.get('component','')}** ({op.get('db_type','')}): `{query}`")
                    for tbl in table_pattern.findall(query):
                        tables.add(tbl.strip('"'))
            else:
                st.markdown("- None")

            st.markdown("##### SQL Summary")
            join_pattern = re.compile(r"\bJOIN\s+([A-Za-z0-9_\.\"]+)\s+.*?\bON\s+(.+?)(?=\bJOIN\b|\bWHERE\b|$)", re.IGNORECASE | re.DOTALL)
            where_pattern = re.compile(r"\bWHERE\s+(.+?)(?=\bGROUP BY\b|\bORDER BY\b|\bHAVING\b|$)", re.IGNORECASE | re.DOTALL)

            joins: list[str] = []
            filters: list[str] = []
            for op in sql_ops:
                query = op.get("query") or ""
                for tbl, cond in join_pattern.findall(query):
                    joins.append(f"{tbl.strip(chr(34))} ON {cond.strip()}")
                for cond in where_pattern.findall(query):
                    filters.append(cond.strip())

            # ── Tables Used ───────────────────────────────────────────────────────────
            st.markdown("**Tables Used**")
            from app.parser.source_target_extractor import extract_sources, extract_targets
            _alias_pattern = re.compile(
                r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([A-Za-z0-9_\.\"]+)\s+(?:AS\s+)?([A-Za-z0-9_]+)",
                re.IGNORECASE,
            )
            _tables_used_rows: list[dict] = []
            _seen_tables: set[str] = set()

            def _add_table_row(table: str, alias: str, purpose: str) -> None:
                key = table.lower()
                if key not in _seen_tables:
                    _seen_tables.add(key)
                    _tables_used_rows.append({"Table": table, "Alias": alias, "Purpose": purpose})

            # Sources → READ
            for src in extract_sources(jd.get("components", [])):
                tbl = src.get("table") or src.get("label") or ""
                if tbl:
                    _add_table_row(tbl, "", f"READ — {src.get('purpose', 'Source table')}")

            # Targets → WRITE
            for tgt in extract_targets(jd.get("components", [])):
                tbl = tgt.get("table") or tgt.get("label") or ""
                if tbl:
                    _add_table_row(tbl, "", f"WRITE — {tgt.get('purpose', 'Target table')}")

            # SQL ops → EXEC (with alias extraction)
            for op in sql_ops:
                query = op.get("query") or ""
                for match in _alias_pattern.finditer(query):
                    tbl = match.group(1).strip('"')
                    alias = match.group(2).strip() if match.group(2) else ""
                    # skip if alias is a SQL keyword
                    if alias.upper() in ("WHERE", "SET", "ON", "AND", "OR", "JOIN", "FROM", "INTO"):
                        alias = ""
                    _add_table_row(tbl, alias, f"EXEC — {op.get('db_type', 'SQL')} via {op.get('component', '')}")
                # also add any plain FROM/INTO tables without alias
                for tbl in table_pattern.findall(query):
                    tbl = tbl.strip('"')
                    _add_table_row(tbl, "", f"EXEC — {op.get('db_type', 'SQL')} via {op.get('component', '')}")

            if _tables_used_rows:
                import pandas as _pd_tu
                st.dataframe(
                    _pd_tu.DataFrame(_tables_used_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.markdown("- None")

            # ── Mapping & Migration Logic ─────────────────────────────────────────────
            import pandas as _pd_map
            from collections import OrderedDict as _OD

            _item_path = job.get("file_path", "")
            _col_map_rows: list[dict] = []
            _map_rules: list[dict] = []
            if _item_path and os.path.isfile(_item_path):
                from app.parser.talend_xml_parser import TalendJobParser as _TJP
                _col_map_rows = _TJP(_item_path).extract_column_mappings()
                _map_rules    = _TJP(_item_path).extract_mapping_rules()

            # ── detect mapping components ─────────────────────────────────────────
            _comps      = jd.get("components", [])
            _has_tmap   = any(c.get("component_type") == "tMap"         for c in _comps)
            _has_tjoin  = any(c.get("component_type") == "tJoin"        for c in _comps)
            _has_tfilt  = any(c.get("component_type") == "tFilterRow"   for c in _comps)
            _has_tagg   = any(c.get("component_type") == "tAggregateRow"for c in _comps)
            _has_lookup = bool(_map_rules and any(r.get("Rule Type") == "Lookup" for r in _map_rules))

            # ── compact signal row ────────────────────────────────────────────────
            _sig_cols = st.columns(5)
            _signals = [
                ("tMap",        _has_tmap,   "🗺️"),
                ("tJoin",       _has_tjoin,  "🔗"),
                ("tFilterRow",  _has_tfilt,  "🔍"),
                ("tAggregate",  _has_tagg,   "Σ"),
                ("Lookup",      _has_lookup, "🔵"),
            ]
            for _sc, (_lbl, _on, _ico) in zip(_sig_cols, _signals):
                _bg = "#e8f5e9" if _on else "#f5f5f5"
                _fg = "#2e7d32" if _on else "#aaa"
                _sc.markdown(
                    f'<div style="background:{_bg};color:{_fg};border-radius:8px;'
                    f'padding:6px 8px;font-size:12px;font-weight:600;text-align:center;">'
                    f'{_ico} {_lbl}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # ── migration logic: rule classification + action ─────────────────────
            _RULE_META = {
                #                          ico   action           bg         fg         effort
                "Direct Copy":            ("✅", "Keep",          "#e8f5e9", "#2e7d32", "Low"),
                "Direct Copy (Nullable)": ("✅", "Keep+Null chk", "#e8f5e9", "#2e7d32", "Low"),
                "Type Cast":              ("⚙️", "tConvertType",  "#fff3e0", "#e65100", "Low"),
                "Context Variable":       ("🔧", "Context bind",  "#e3f2fd", "#1565c0", "Low"),
                "Join Key":               ("🔗", "Remap key",     "#f3e5f5", "#6a1b9a", "Medium"),
                "Conditional Expression": ("🔀", "Rewrite expr",  "#fff8e1", "#f57f17", "High"),
                "String Concatenation":   ("✏️", "CONCAT expr",   "#fce4ec", "#880e4f", "Low"),
                "Function Transform":     ("🛠️", "Migrate func",  "#e0f2f1", "#00695c", "High"),
                "Arithmetic Expression":  ("🧮", "Port arith",    "#fff3e0", "#bf360c", "Medium"),
                "Cross-Table Reference":  ("🌐", "Cross-schema",  "#e8eaf6", "#283593", "High"),
                "Expression Mapping":     ("📝", "Manual review", "#f5f5f5", "#424242", "Medium"),
            }
            _EFFORT_BADGE = {
                "Low":    ("#e8f5e9", "#2e7d32", "🟢 Low"),
                "Medium": ("#fff3e0", "#e65100", "🟡 Medium"),
                "High":   ("#fde8e8", "#b71c1c", "🔴 High"),
            }
            _RULE_GUIDE = {
                "Direct Copy":            "No change needed.",
                "Direct Copy (Nullable)": "Add null-check in tMap if strict mode.",
                "Type Cast":              "Apply CAST / tConvertType; verify precision.",
                "Context Variable":       "Bind to Cloud context group / env var.",
                "Join Key":               "Confirm key in migrated schema; update lookup input.",
                "Conditional Expression": "Translate CASE/IF to tMap expression or tJavaRow.",
                "String Concatenation":   "Rewrite with StringHandling.CONCAT.",
                "Function Transform":     "Validate function in target runtime; replace deprecated.",
                "Arithmetic Expression":  "Port to tMap expression; check overflow.",
                "Cross-Table Reference":  "Verify table accessible in new env; update DB conn.",
                "Expression Mapping":     "Migrate to tMap expression editor manually.",
            }

            # rule counts
            _rule_counts: dict[str, int] = {}
            for _r in _col_map_rows:
                _rule_counts[_r["Migration Rule"]] = _rule_counts.get(_r["Migration Rule"], 0) + 1

            # ── migration logic summary table ─────────────────────────────────────
            st.markdown("**Migration Logic**")
            if _rule_counts:
                _auto_n  = sum(n for r, n in _rule_counts.items() if "Direct Copy" in r)
                _total_n = sum(_rule_counts.values())
                _pct     = round(100 * _auto_n / _total_n) if _total_n else 0
                _c1, _c2 = st.columns([3, 1])
                with _c1:
                    st.progress(_pct / 100)
                with _c2:
                    st.markdown(
                        f'<div style="font-size:12px;font-weight:700;color:#2e7d32;'
                        f'padding-top:4px;">{_pct}% auto-migrate</div>',
                        unsafe_allow_html=True,
                    )

                # effort summary chips
                _eff_counts = {"Low": 0, "Medium": 0, "High": 0}
                for _rule, _cnt in _rule_counts.items():
                    _eff = _RULE_META.get(_rule, ("","","","","Medium"))[4]
                    _eff_counts[_eff] = _eff_counts.get(_eff, 0) + _cnt
                _chip_html = ""
                for _eff in ("Low", "Medium", "High"):
                    _ebg, _efg, _elbl = _EFFORT_BADGE[_eff]
                    _ecnt = _eff_counts.get(_eff, 0)
                    if _ecnt:
                        _chip_html += (
                            f'<span style="background:{_ebg};color:{_efg};font-size:11px;'
                            f'font-weight:700;padding:2px 10px;border-radius:20px;margin:0 4px 0 0;">'
                            f'{_elbl} — {_ecnt} col{"s" if _ecnt != 1 else ""}</span>'
                        )
                st.markdown(f'<div style="margin:4px 0 8px 0">{_chip_html}</div>', unsafe_allow_html=True)

                _logic_rows = []
                for _rule, _cnt in sorted(_rule_counts.items(), key=lambda x: -x[1]):
                    _ico, _action, _bg, _fg, _eff = _RULE_META.get(_rule, ("📝","Manual review","#f5f5f5","#424242","Medium"))
                    _guide = _RULE_GUIDE.get(_rule, "Manual review required.")
                    _logic_rows.append({
                        "Rule": _rule,
                        "Cols": _cnt,
                        "Effort": _eff,
                        "Action": _action,
                        "Guidance": _guide,
                    })

                st.dataframe(
                    _pd_map.DataFrame(_logic_rows),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Cols":    st.column_config.NumberColumn(width="small"),
                        "Effort":  st.column_config.TextColumn(width="small"),
                        "Action":  st.column_config.TextColumn(width="medium"),
                        "Guidance":st.column_config.TextColumn(width="large"),
                    },
                )
            elif _has_tmap or _has_tjoin:
                st.caption("tMap/tJoin detected — load .item file for column-level logic.")
            else:
                st.caption("No mapping components detected.")

            # ── column mapping by component pair ─────────────────────────────────
            if _col_map_rows:
                st.markdown("**Column Mapping**")
                _cm_groups = _OD()
                for _row in _col_map_rows:
                    _gkey = (_row["Source Component"], _row["Target Component"])
                    _cm_groups.setdefault(_gkey, []).append(_row)
                for (_src_c, _tgt_c), _rows in _cm_groups.items():
                    _n = len(_rows)
                    with st.expander(f"📦 {_src_c} → {_tgt_c}  ({_n})", expanded=False):
                        _rules_here = list(dict.fromkeys(r["Migration Rule"] for r in _rows))
                        _bhtml = ""
                        for _rl in _rules_here:
                            _, _, _bg, _fg, _ = _RULE_META.get(_rl, ("📝","",  "#f5f5f5","#424242","Medium"))
                            _bhtml += (
                                f'<span style="background:{_bg};color:{_fg};font-size:10px;'
                                f'font-weight:700;padding:1px 8px;border-radius:20px;margin:0 3px 3px 0;">'
                                f'{_rl}</span>'
                            )
                        st.markdown(f'<div style="margin-bottom:6px">{_bhtml}</div>', unsafe_allow_html=True)
                        st.dataframe(
                            _pd_map.DataFrame(_rows, columns=["Source Column","Target Column","Migration Rule"]),
                            use_container_width=True, hide_index=True,
                        )

            # ── mapping rules (join/lookup/reject) ────────────────────────────────
            if _map_rules:
                st.markdown("**Mapping Rules**")
                _mr_icon = {"Output":"🟢","Lookup":"🔵","Reject":"🔴","Expression Filter":"🟡"}
                _mr_grp: dict = {}
                for _mr in _map_rules:
                    _mr_grp.setdefault(_mr["Rule Type"], []).append(_mr)
                for _rtype, _rrows in _mr_grp.items():
                    with st.expander(f"{_mr_icon.get(_rtype,'⚪')} {_rtype} ({len(_rrows)})", expanded=False):
                        st.dataframe(
                            _pd_map.DataFrame(_rrows, columns=["Table","Join Type","Match Mode","Filter Expression"]),
                            use_container_width=True, hide_index=True,
                        )

            st.markdown("**Joins**")
            if joins:
                for j in joins:
                    st.markdown(f"- {j}")
            else:
                st.markdown("- None")

            st.markdown("**Filters**")
            if filters:
                for f in filters:
                    st.markdown(f"- {f}")
            else:
                st.markdown("- None")

            st.markdown("#### Functional Flow")
            comp_by_id = {c.get("unique_name"): c for c in jd.get("components", []) if isinstance(c, dict)}
            g = nx.DiGraph()
            for uid, c in comp_by_id.items():
                g.add_node(uid)
            for conn in jd.get("connections", []):
                src, tgt = conn.get("source"), conn.get("target")
                if src in comp_by_id and tgt in comp_by_id:
                    g.add_edge(src, tgt)

            try:
                order = list(nx.topological_sort(g))
            except nx.NetworkXUnfeasible:
                order = list(g.nodes)

            if order:
                for i, uid in enumerate(order, start=1):
                    c = comp_by_id.get(uid, {})
                    ctype = c.get("component_type", "Unknown")
                    st.markdown(f"{i}. **{ctype}** ({uid})")
            else:
                st.markdown("- None")

            st.markdown("#### Technical Flowchart")

            def _node_id(name: str) -> str:
                return re.sub(r"[^A-Za-z0-9_]", "_", str(name))

            mermaid_lines = ["graph LR"]
            for uid, c in comp_by_id.items():
                ctype = c.get("component_type", "Unknown")
                mermaid_lines.append(f'    {_node_id(uid)}["{ctype}\\n{uid}"]')
            for conn in jd.get("connections", []):
                src, tgt = conn.get("source"), conn.get("target")
                if src in comp_by_id and tgt in comp_by_id:
                    label = conn.get("connector") or ""
                    mermaid_lines.append(f'    {_node_id(src)} -->|{label}| {_node_id(tgt)}')

            if comp_by_id:
                flow_mermaid_code = "\n".join(mermaid_lines)
                _render_mermaid(flow_mermaid_code, height=420)
            else:
                st.markdown("- None")

            st.markdown("#### Business Logic")

            bl_filters, bl_lookups, bl_joins, bl_rules = [], [], [], []
            bl_aggregations: list[dict] = []

            _AGG_BUSINESS_MEANING = {
                "SUM":   "Totals a numeric field — used for revenue, quantities, or any additive measure.",
                "COUNT": "Counts records or non-null values — used for volume, frequency, or occurrence metrics.",
                "AVG":   "Computes the arithmetic mean — used for averages such as price, duration, or score.",
                "MIN":   "Finds the smallest value — used for earliest date, lowest price, or minimum threshold.",
                "MAX":   "Finds the largest value — used for latest date, peak value, or maximum threshold.",
            }

            for c in jd.get("components", []):
                ctype = c.get("component_type", "")
                uid = c.get("unique_name", ctype)
                params = component_parameters(c)

                if ctype == "tFilterRow":
                    cond = params.get("CONDITION") or params.get("FILTER_CONDITION") or "condition defined in component"
                    bl_filters.append(f"{uid}: {cond}")

                if ctype in ("tJoin", "tMap"):
                    for key, value in params.items():
                        if "JOIN" in key.upper() and value:
                            bl_joins.append(f"{uid} [{key}]: {value}")

                if ctype in ("tMap",):
                    for key, value in params.items():
                        if "EXPRESSION" in key.upper() and value:
                            bl_rules.append(f"{uid} [{key}]: {value}")

                if ctype == "tAggregateRow":
                    # Extract GROUP_BY columns
                    group_cols: list[str] = []
                    for key, value in params.items():
                        if "GROUP" in key.upper() and value:
                            raw = str(value)
                            cols = re.findall(r'"([^"]+)"', raw) or [raw]
                            group_cols.extend(cols)

                    # Extract aggregate operations (FUNCTION + OUTPUT_COLUMN pairs)
                    func_keys  = sorted([k for k in params if re.search(r"FUNCTION",  k, re.I)])
                    col_keys   = sorted([k for k in params if re.search(r"OUTPUT_COL|AGG_COL|COLUMN_NAME", k, re.I)])
                    input_keys = sorted([k for k in params if re.search(r"INPUT_COL|FIELD_NAME", k, re.I)])

                    ops: list[dict] = []
                    for i, fk in enumerate(func_keys):
                        func = str(params.get(fk, "")).upper()
                        func = re.sub(r"[^A-Z_]", "", func)
                        output_col = ""
                        input_col = ""
                        if i < len(col_keys):
                            raw = str(params.get(col_keys[i], ""))
                            output_col = (re.findall(r'"([^"]+)"', raw) or [raw])[0]
                        if i < len(input_keys):
                            raw = str(params.get(input_keys[i], ""))
                            input_col = (re.findall(r'"([^"]+)"', raw) or [raw])[0]
                        if func:
                            ops.append({"func": func, "output": output_col, "input": input_col})

                    # Fallback: scan all param values for AGG patterns
                    if not ops:
                        raw_all = " ".join(str(v) for v in params.values())
                        for m in re.finditer(r'\b(SUM|COUNT|AVG|MIN|MAX)\b.*?"([^"]+)"', raw_all, re.I):
                            ops.append({"func": m.group(1).upper(), "output": m.group(2), "input": ""})

                    if ops or group_cols:
                        bl_aggregations.append({"uid": uid, "group_by": group_cols, "ops": ops})

            for conn in jd.get("connections", []):
                if (conn.get("connector") or "").upper() == "LOOKUP":
                    src = comp_by_id.get(conn.get("source"), {})
                    tgt = comp_by_id.get(conn.get("target"), {})
                    bl_lookups.append(
                        f"{src.get('component_type','?')} ({conn.get('source')}) → "
                        f"{tgt.get('component_type','?')} ({conn.get('target')})"
                    )

            def _bl_section(title, items):
                st.markdown(f"**{title}**")
                if items:
                    for it in items:
                        st.markdown(f"- {it}")
                else:
                    st.markdown("- None")

            _bl_section("Filters", bl_filters)
            _bl_section("Lookups", bl_lookups)
            _bl_section("Joins", bl_joins)
            _bl_section("Rules", bl_rules)

            # ── Aggregations ──────────────────────────────────────────────────────────
            st.markdown("**Aggregations**")
            if bl_aggregations:
                import pandas as _pd_agg
                for agg in bl_aggregations:
                    st.markdown(f"*{agg['uid']}*")
                    if agg["group_by"]:
                        st.markdown(f"  - **Group By:** {', '.join(agg['group_by'])}")
                    if agg["ops"]:
                        rows = []
                        for op in agg["ops"]:
                            func = op["func"]
                            expr = f"{func}({op['input']})" if op["input"] else func
                            output = op["output"] or "—"
                            meaning = _AGG_BUSINESS_MEANING.get(func, "Aggregate operation.")
                            rows.append({"Function": expr, "Output Column": output, "Business Meaning": meaning})
                        st.dataframe(_pd_agg.DataFrame(rows), use_container_width=True, hide_index=True)
                    else:
                        st.markdown("  - Aggregate component detected; operation details not parseable from parameters.")
            else:
                st.markdown("- None")

            # ── Business Flowchart ────────────────────────────────────────────────────
            st.markdown("#### Business Flowchart")

            def _biz_node(name: str) -> str:
                """Return a safe Mermaid node id."""
                return re.sub(r"[^A-Za-z0-9_]", "_", str(name))

            # Collect Source nodes (named from inventory)
            biz_sources = [s["name"] for s in inv.get("sources", [])] or (
                [s for s in inv.get("source_names", [])]
            )
            # Collect Target nodes (named from inventory)
            biz_targets = [t["name"] for t in inv.get("targets", [])] or (
                [t for t in inv.get("target_names", [])]
            )

            # Validation nodes — tFilterRow components
            validation_comps = [
                c.get("unique_name", c.get("component_type", "Filter"))
                for c in jd.get("components", [])
                if c.get("component_type") == "tFilterRow"
            ]

            # Transformation nodes — tMap / tJoin / tSortRow / tAggregateRow / tNormalize
            TRANSFORM_TYPES = {"tMap", "tJoin", "tSortRow", "tAggregateRow", "tNormalize", "tConvertType", "tReplace"}
            transform_comps = [
                c.get("unique_name", c.get("component_type", "Transform"))
                for c in jd.get("components", [])
                if c.get("component_type") in TRANSFORM_TYPES
            ]

            biz_mermaid = ["graph LR"]

            # Source nodes
            for s in biz_sources:
                nid = "SRC_" + _biz_node(s)
                biz_mermaid.append(f'    {nid}[("📥 {s}")]')

            # Validation nodes
            for v in validation_comps:
                nid = "VAL_" + _biz_node(v)
                biz_mermaid.append(f'    {nid}{{"✅ {v}"}}')

            # Transformation nodes
            for tr in transform_comps:
                nid = "TRF_" + _biz_node(tr)
                biz_mermaid.append(f'    {nid}["⚙️ {tr}"]')

            # Target nodes
            for t in biz_targets:
                nid = "TGT_" + _biz_node(t)
                biz_mermaid.append(f'    {nid}[("📤 {t}")]')

            # Edges: Source → Validation (if any) → Transformation (if any) → Target
            # Fall back gracefully when stages are empty
            if biz_sources or validation_comps or transform_comps or biz_targets:
                stage_groups = []
                if biz_sources:
                    stage_groups.append([("SRC_" + _biz_node(s), s) for s in biz_sources])
                if validation_comps:
                    stage_groups.append([("VAL_" + _biz_node(v), v) for v in validation_comps])
                if transform_comps:
                    stage_groups.append([("TRF_" + _biz_node(tr), tr) for tr in transform_comps])
                if biz_targets:
                    stage_groups.append([("TGT_" + _biz_node(t), t) for t in biz_targets])

                # Connect last node of each stage to first node of next stage
                for i in range(len(stage_groups) - 1):
                    from_nodes = stage_groups[i]
                    to_nodes = stage_groups[i + 1]
                    for fn, _ in from_nodes:
                        for tn, _ in to_nodes:
                            biz_mermaid.append(f"    {fn} --> {tn}")

                biz_mermaid_code = "\n".join(biz_mermaid)
                _render_mermaid(biz_mermaid_code, height=420)
            else:
                st.markdown("- No business flow could be determined for this job.")

        with _ov_func:
            st.markdown("### Functional Overview")
            functional_sources = [s.get("name", "") for s in inv.get("sources", []) if s.get("name")]
            functional_targets = [t.get("name", "") for t in inv.get("targets", []) if t.get("name")]
            functional_sql = _sql_ops
            functional_steps = _flow_steps

            if functional_sources and functional_targets:
                st.info(
                    f"{job_name} reads from {', '.join(functional_sources)} and writes to "
                    f"{', '.join(functional_targets)} through {len(functional_steps)} detected processing step(s)."
                )
            elif functional_sources:
                st.info(
                    f"{job_name} reads from {', '.join(functional_sources)} and performs internal processing "
                    f"through {len(functional_steps)} detected step(s)."
                )
            elif functional_targets:
                st.info(
                    f"{job_name} produces output for {', '.join(functional_targets)} through "
                    f"{len(functional_steps)} detected processing step(s)."
                )
            else:
                st.info(f"{job_name} contains {len(jd.get('components', []))} component(s) with no explicit source or target metadata detected.")

            render_kpi_row([
                {"label": "Sources", "value": str(len(functional_sources)), "caption": "Detected inputs"},
                {"label": "Targets", "value": str(len(functional_targets)), "caption": "Detected outputs"},
                {"label": "SQL Queries", "value": str(len(functional_sql)), "caption": "Executable SQL"},
                {"label": "Components", "value": str(len(jd.get("components", []))), "caption": "Job steps"},
            ])

            st.markdown("### Source To Target")
            left, right = st.columns(2)
            with left:
                st.markdown("**Source Tables / Files**")
                if functional_sources:
                    for source in functional_sources:
                        st.markdown(f"- {source}")
                else:
                    st.markdown("- None detected")
            with right:
                st.markdown("**Target Tables / Files**")
                if functional_targets:
                    for target in functional_targets:
                        st.markdown(f"- {target}")
                else:
                    st.markdown("- None detected")

            st.markdown("### Processing Steps")
            if functional_steps:
                for idx, (icon, title, detail) in enumerate(functional_steps, start=1):
                    st.markdown(f"{idx}. **{title}** - {detail}")
            else:
                st.markdown("- No processing steps detected")

            st.markdown("### Functional Rules")
            rules_found = False
            for c in jd.get("components", []):
                ctype = c.get("component_type", "")
                uid = c.get("unique_name", ctype)
                params = component_parameters(c)
                rule_params = {
                    key: value for key, value in params.items()
                    if value and any(token in key.upper() for token in ("QUERY", "CONDITION", "FILTER", "EXPRESSION", "JOIN", "TABLE"))
                }
                if rule_params:
                    rules_found = True
                    with st.expander(f"{ctype} ({uid})", expanded=False):
                        for key, value in rule_params.items():
                            st.markdown(f"**{key}:** `{str(value)[:500]}`")
            if not rules_found:
                st.markdown("- No explicit functional rules detected in component parameters")


    if _cat_sel == "Executive & Migration":
        # Compute variables that are normally set inside Overview/_ov_exec tab
        _em_complexity = job.get("complexity", {})
        _em_level = _em_complexity.get("complexity", "LOW")
        _em_score = _em_complexity.get("score", "—")
        _em_risk_factors = _em_complexity.get("risk_factors", [])
        effort_hours = EFFORT_HOURS["manual"] if _em_level in ("HIGH", "CRITICAL") else EFFORT_HOURS["auto"]
        _cloud_readiness = "Not Ready" if effort_hours == EFFORT_HOURS["manual"] else "Ready"
        _em_job_recs = [r for r in _all_recs if r["job_name"] == job_name]
        auto_fixes = [r for r in _em_job_recs if r["auto_fix"]]
        manual_fixes = [r for r in _em_job_recs if not r["auto_fix"]]
        _em_inv = _inv
        _em_sql_ops = _em_inv.get("sql_operations", [])
        _em_component_count = len(jd.get("components", []))
        _em_custom_code_count = sum(
            1 for c in jd.get("components", [])
            if c.get("component_type", "") in ("tJava", "tJavaFlex", "tJavaRow")
        )
        _em_dependency_count = len(jd.get("connections", []))
        _em_unsupported = [r for r in _em_job_recs if r.get("severity") in ("HIGH", "CRITICAL")]
        complexity_details = {
            "components": {
                "Components": _em_component_count,
                "SQL Logic": len(_em_sql_ops),
                "Dependencies": _em_dependency_count,
                "Custom Code": _em_custom_code_count,
                "Migration Risk": len(_em_risk_factors),
            },
            "total_score": _em_score,
            "notes": "Derived from parsed components, SQL operations, dependencies, custom code, and risk factors.",
        }
        effort_details = {
            "hours": {
                "Analysis Hours": 2,
                "SQL Conversion": len(_em_sql_ops) * 2,
                "Component Migration": max(1, _em_component_count // 5),
                "Testing": 4 if effort_hours == EFFORT_HOURS["manual"] else 1,
                "Validation": 2,
            },
            "total_hours": effort_hours,
            "notes": "Total hours use the configured migration effort setting for this complexity class.",
        }
        # Keep level in scope for the rest of this block
        level = _em_level
        cloud_readiness_colors = {
            "Ready": ("#f0fdf4", "#15803d"),
            "Not Ready": ("#fff1f2", "#be123c"),
        }

        _em_exec, _em_migration, _em_cop, _em_mig, _em_valid = st.tabs(["Executive Flow", "Migration", "AI Copilot", "Migration Assessment", "Validation"])
        with _em_exec:
            _exec_recs = [r for r in _all_recs if r["job_name"] == job_name]
            render_executive_job_360(
                job=job,
                jd=jd,
                inv=_inv,
                recs=_exec_recs,
                job_name=job_name,
                show_export=True,
            )

        with _em_migration:
            # ── Migration Impact ───────────────────────────────────────────────────
            st.markdown("#### 🎯 Migration Impact")
            st.markdown(
                """
                <style>
                .mi-wrap{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px;}
                .mi-card{background:#fff;border:1px solid #e4e3dc;border-radius:10px;
                    padding:14px 18px;min-width:150px;flex:1;}
                .mi-label{font-size:11px;font-weight:700;letter-spacing:.07em;
                    text-transform:uppercase;color:#8a8a85;margin-bottom:4px;}
                .mi-value{font-size:28px;font-weight:800;color:#1a1a18;line-height:1.1;}
                .mi-sub{font-size:11px;color:#9e9e96;margin-top:3px;}
                .mi-badge-AUTO{display:inline-block;padding:3px 10px;border-radius:20px;
                    font-size:12px;font-weight:700;background:#d4edda;color:#155724;}
                .mi-badge-MANUAL{display:inline-block;padding:3px 10px;border-radius:20px;
                    font-size:12px;font-weight:700;background:#fff3cd;color:#856404;}
                .mi-badge-BLOCKED{display:inline-block;padding:3px 10px;border-radius:20px;
                    font-size:12px;font-weight:700;background:#f8d7da;color:#721c24;}
                .mi-item{background:#fff;border:1px solid #e4e3dc;border-radius:8px;
                    padding:8px 12px;margin-bottom:6px;display:flex;justify-content:space-between;
                    align-items:center;font-size:12px;}
                .mi-item-name{font-weight:600;color:#1a1a18;}
                .mi-item-tag{font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;}
                .mi-tag-vendor{background:#e0f0ff;color:#0369a1;}
                .mi-tag-unsupported{background:#fce7f3;color:#9d174d;}
                .mi-tag-manual{background:#fff3cd;color:#92400e;}
                </style>
                """,
                unsafe_allow_html=True,
            )

            # ── Compute Migration Impact metrics ────────────────────────────────
            _mi_sql_ops = _sql_ops
            _mi_comps = jd.get("components", [])
            _mi_total_comps = len(_mi_comps)

            # Vendor-specific SQL functions (dialect-specific, non-standard)
            _VENDOR_FUNCS = {
                # Oracle
                "NVL", "NVL2", "DECODE", "ROWNUM", "ROWID", "SYSDATE", "SYSTIMESTAMP",
                "CONNECT_BY_ROOT", "PRIOR", "SYS_GUID", "DBMS_",
                # SQL Server
                "ISNULL", "GETDATE", "GETUTCDATE", "NEWID", "CHARINDEX", "PATINDEX",
                "DATEPART", "DATEDIFF", "STUFF", "IIF", "FORMAT",
                # MySQL
                "IFNULL", "GROUP_CONCAT", "NOW", "DATE_FORMAT", "STR_TO_DATE",
                "UNIX_TIMESTAMP", "FROM_UNIXTIME", "FIELD", "FIND_IN_SET",
                # PostgreSQL
                "GENERATE_SERIES", "STRING_AGG", "ARRAY_AGG", "UNNEST",
                "EXTRACT", "DATE_TRUNC", "TO_CHAR", "TO_DATE", "TO_TIMESTAMP",
                # Snowflake / BigQuery / Redshift
                "QUALIFY", "LISTAGG", "MEDIAN", "APPROXIMATE_COUNT_DISTINCT",
                "APPROX_COUNT_DISTINCT", "SAFE_CAST", "PARSE_DATE", "TIMESTAMP_TRUNC",
            }
            _mi_vendor_funcs = set()
            for _op in _mi_sql_ops:
                _sql_upper = str(_op.get("query", "")).upper()
                for _vf in _VENDOR_FUNCS:
                    if re.search(r"\b" + re.escape(_vf) + r"\b", _sql_upper):
                        _mi_vendor_funcs.add(_vf)

            # Unsupported SQL patterns for cloud/T8 migration
            _UNSUPPORTED_PATTERNS = {
                "MERGE statement": r"\bMERGE\s+INTO\b",
                "Cursor / FETCH": r"\b(DECLARE\s+\w+\s+CURSOR|FETCH\s+NEXT)\b",
                "Temp tables (#)": r"\bCREATE\s+(?:LOCAL\s+)?TEMP(?:ORARY)?\s+TABLE\b|#\w+",
                "Stored proc EXEC": r"\b(EXEC|EXECUTE)\s+\w+",
                "GOTO statement": r"\bGOTO\b",
                "Dynamic SQL": r"\bEXEC\s*\(\s*@|EXECUTE\s*\(\s*N?'",
                "DB Link / @dblink": r"@[A-Za-z0-9_]+\s*\.",
                "ROWNUM / ROWID": r"\b(ROWNUM|ROWID)\b",
                "CONNECT BY": r"\bCONNECT\s+BY\b",
                "Hierarchical query": r"\bSTART\s+WITH\b",
                "PIVOT / UNPIVOT": r"\b(PIVOT|UNPIVOT)\s*\(",
                "XML functions": r"\b(XMLELEMENT|XMLAGG|XMLTYPE|FOR\s+XML)\b",
            }
            _mi_unsupported = {}
            for _op in _mi_sql_ops:
                _sql_raw = str(_op.get("query", ""))
                for _label, _pat in _UNSUPPORTED_PATTERNS.items():
                    if re.search(_pat, _sql_raw, flags=re.IGNORECASE):
                        _mi_unsupported[_label] = _mi_unsupported.get(_label, 0) + 1

            # Auto-migratable components (standard, well-supported)
            _AUTO_COMP_TYPES = {
                "tDBInput", "tDBOutput", "tDBRow", "tFileInputDelimited", "tFileOutputDelimited",
                "tMap", "tSortRow", "tAggregateRow", "tFilterRow", "tUnite", "tLogRow",
                "tFlowToIterate", "tIterateToFlow", "tConvertType", "tReplace", "tNormalize",
                "tFileInputJSON", "tFileOutputJSON", "tFileInputXML", "tFileOutputXML",
            }
            _MANUAL_COMP_TYPES = {
                "tJava", "tJavaFlex", "tJavaRow", "tSystem", "tRunJob",
                "tSendMail", "tFTP", "tSFTP", "tHTTP", "tRESTClient",
            }
            _mi_auto_comps = [c for c in _mi_comps if c.get("component_type", "") in _AUTO_COMP_TYPES]
            _mi_manual_comps = [c for c in _mi_comps if c.get("component_type", "") in _MANUAL_COMP_TYPES]
            _mi_unknown_comps = [
                c for c in _mi_comps
                if c.get("component_type", "") not in _AUTO_COMP_TYPES
                and c.get("component_type", "") not in _MANUAL_COMP_TYPES
            ]

            _mi_auto_pct = round(len(_mi_auto_comps) / max(_mi_total_comps, 1) * 100)
            _mi_manual_review_count = len(_mi_manual_comps) + len(_mi_unknown_comps)

            # Overall migration mode
            _has_blockers = bool(_mi_unsupported) or bool(_mi_vendor_funcs)
            if _mi_auto_pct >= 70 and not _has_blockers:
                _mi_mode = "AUTO"
                _mi_mode_caption = "Strong candidate for automated migration"
            elif _mi_auto_pct >= 40 or (_mi_manual_review_count <= 3 and not _mi_unsupported):
                _mi_mode = "MANUAL"
                _mi_mode_caption = "Partial automation — manual review required"
            else:
                _mi_mode = "BLOCKED"
                _mi_mode_caption = "Complex migration — significant manual effort expected"

            # ── KPI row ────────────────────────────────────────────────────────
            mi_c1, mi_c2, mi_c3, mi_c4 = st.columns(4)
            with mi_c1:
                st.markdown(
                    f'<div class="mi-card"><div class="mi-label">Auto %</div>'
                    f'<div class="mi-value">{_mi_auto_pct}%</div>'
                    f'<div class="mi-sub">{len(_mi_auto_comps)} of {_mi_total_comps} components</div></div>',
                    unsafe_allow_html=True,
                )
            with mi_c2:
                st.markdown(
                    f'<div class="mi-card"><div class="mi-label">Manual Review</div>'
                    f'<div class="mi-value">{_mi_manual_review_count}</div>'
                    f'<div class="mi-sub">components need review</div></div>',
                    unsafe_allow_html=True,
                )
            with mi_c3:
                st.markdown(
                    f'<div class="mi-card"><div class="mi-label">Vendor Functions</div>'
                    f'<div class="mi-value">{len(_mi_vendor_funcs)}</div>'
                    f'<div class="mi-sub">dialect-specific detected</div></div>',
                    unsafe_allow_html=True,
                )
            with mi_c4:
                st.markdown(
                    f'<div class="mi-card"><div class="mi-label">Unsupported SQL</div>'
                    f'<div class="mi-value">{len(_mi_unsupported)}</div>'
                    f'<div class="mi-sub">pattern(s) flagged</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown(
                f'<div style="margin:8px 0 18px;">'
                f'<span class="mi-badge-{_mi_mode}">{_mi_mode}</span>'
                f' &nbsp;<span style="font-size:13px;color:#5a5a56;">{_mi_mode_caption}</span></div>',
                unsafe_allow_html=True,
            )

            # ── Detail sections ─────────────────────────────────────────────────
            mi_left, mi_right = st.columns(2)

            with mi_left:
                st.markdown("**🔧 Manual Review Components**")
                _review_list = _mi_manual_comps + _mi_unknown_comps
                if _review_list:
                    for _rc in _review_list:
                        _rtype = _rc.get("component_type", "Unknown")
                        _rname = _rc.get("unique_name", _rtype)
                        _rtag = "manual" if _rc in _mi_manual_comps else "manual"
                        st.markdown(
                            f'<div class="mi-item"><span class="mi-item-name">{html_lib.escape(_rname)}</span>'
                            f'<span class="mi-item-tag mi-tag-{_rtag}">{html_lib.escape(_rtype)}</span></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown('<div style="font-size:13px;color:#9e9e96;font-style:italic;">None detected</div>', unsafe_allow_html=True)

                st.markdown("**🏷️ Vendor Functions**")
                if _mi_vendor_funcs:
                    for _vf in sorted(_mi_vendor_funcs):
                        st.markdown(
                            f'<div class="mi-item"><span class="mi-item-name">{html_lib.escape(_vf)}</span>'
                            f'<span class="mi-item-tag mi-tag-vendor">vendor</span></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown('<div style="font-size:13px;color:#9e9e96;font-style:italic;">None detected</div>', unsafe_allow_html=True)

            with mi_right:
                st.markdown("**🚫 Unsupported SQL Patterns**")
                if _mi_unsupported:
                    for _ul, _uc in sorted(_mi_unsupported.items()):
                        _occur = f"{_uc} occurrence{'s' if _uc > 1 else ''}"
                        st.markdown(
                            f'<div class="mi-item"><span class="mi-item-name">{html_lib.escape(_ul)}</span>'
                            f'<span class="mi-item-tag mi-tag-unsupported">{_occur}</span></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown('<div style="font-size:13px;color:#9e9e96;font-style:italic;">None detected</div>', unsafe_allow_html=True)

                st.markdown("**✅ Auto-Migratable Components**")
                if _mi_auto_comps:
                    for _ac in _mi_auto_comps[:10]:
                        _atype = _ac.get("component_type", "")
                        _aname = _ac.get("unique_name", _atype)
                        st.markdown(
                            f'<div class="mi-item"><span class="mi-item-name">{html_lib.escape(_aname)}</span>'
                            f'<span class="mi-item-tag" style="background:#d4edda;color:#155724;">{html_lib.escape(_atype)}</span></div>',
                            unsafe_allow_html=True,
                        )
                    if len(_mi_auto_comps) > 10:
                        st.markdown(f'<div style="font-size:11px;color:#9e9e96;margin-top:4px;">… and {len(_mi_auto_comps)-10} more</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="font-size:13px;color:#9e9e96;font-style:italic;">None detected</div>', unsafe_allow_html=True)

            st.markdown("---")

            # ── Cloud Readiness ────────────────────────────────────
            st.markdown("#### Cloud Readiness")
            _readiness_label = "not ready for automated migration" if effort_hours == EFFORT_HOURS["manual"] else "a good candidate for automated migration"
            _fix_summary = f"{len(auto_fixes)} issue(s) can be auto-fixed and {len(manual_fixes)} require manual review" if (auto_fixes or manual_fixes) else "no issues detected"
            st.markdown(
                f'<p style="font-size:13px;color:#5a5a56;margin-bottom:12px;">'
                f'This job is <strong>{_readiness_label}</strong> based on its {level.lower()} complexity '
                f'and an estimated effort of {effort_hours}h. {_fix_summary.capitalize()}.</p>',
                unsafe_allow_html=True,
            )
            _cr_bg, _cr_fg = cloud_readiness_colors.get(_cloud_readiness, ("#EEF2FF", "#3730A3"))
            render_kpi_row([
                {"label": "Complexity", "value": level, "caption": f"Status: {level}", "color": "#b45309", "details": complexity_details},
                {"label": "Migration Effort", "value": f"{effort_hours}h", "caption": "Manual" if effort_hours == EFFORT_HOURS["manual"] else "Auto-migratable", "color": "#6d28d9", "details": effort_details},
                {"label": "Auto Fixes", "value": str(len(auto_fixes)), "caption": "issue(s) auto-fixable"},
                {"label": "Manual Fixes", "value": str(len(manual_fixes)), "caption": "issue(s) need review"},
            ])

            # ── Migration Waves ────────────────────────────────────
            st.markdown("#### Migration Waves")
            st.caption("Wave order derived from existing job dependency relationships (jobs with no unresolved dependencies migrate first).")

            def _compute_migration_waves(jobs):
                names = {j["job_data"]["job_name"] for j in jobs}
                deps = {
                    j["job_data"]["job_name"]: set(j.get("dependencies", {}).get("child_jobs", [])) & names
                    for j in jobs
                }
                remaining = set(names)
                assigned = set()
                waves = []
                while remaining:
                    wave = {n for n in remaining if deps[n] <= assigned}
                    if not wave:
                        wave = set(remaining)
                    waves.append(sorted(wave))
                    assigned |= wave
                    remaining -= wave
                return waves

            _waves = _compute_migration_waves(all_jobs)
            _wave_cols = st.columns(max(len(_waves), 1))
            for _wi, _wjobs in enumerate(_waves):
                with _wave_cols[_wi]:
                    st.markdown(f"**Wave {_wi + 1}**")
                    for _wn in _wjobs:
                        _is_current = _wn == job_name
                        _bg = "#3C3489" if _is_current else "#EEEDFE"
                        _fg = "#fff" if _is_current else "#3C3489"
                        st.markdown(
                            f'<div style="background:{_bg};color:{_fg};font-size:12px;font-weight:600;'
                            f'padding:5px 10px;border-radius:8px;margin-bottom:4px;">{_wn}</div>',
                            unsafe_allow_html=True,
                        )

            st.markdown("#### Recommended Migration Sequence")
            _sequence = [n for _wjobs in _waves for n in _wjobs]
            for _si, _sn in enumerate(_sequence, start=1):
                _is_current = _sn == job_name
                _marker = "➡️" if _is_current else f"{_si}."
                _suffix = " **(this job)**" if _is_current else ""
                st.markdown(f"{_marker} {_sn}{_suffix}")

            st.markdown("#### Recommendations")
            all_recs = _all_recs
            job_recs = [r for r in all_recs if r["job_name"] == job_name]
            auto_fixes = [r for r in job_recs if r["auto_fix"]]
            manual_fixes = [r for r in job_recs if not r["auto_fix"]]

            st.markdown("**Auto Fixes**")
            if auto_fixes:
                for r in auto_fixes:
                    st.markdown(f"- {r['issue']}: {r['fix']}")
            else:
                st.markdown("- None")

            st.markdown("**Manual Fixes**")
            if manual_fixes:
                for r in manual_fixes:
                    st.markdown(f"- {r['issue']}: {r['fix']}")
            else:
                st.markdown("- None")

            st.markdown("---")
            _auto_fix_text = "\n".join(f"- {r['issue']}: {r['fix']}" for r in auto_fixes) or "- None"
            _manual_fix_text = "\n".join(f"- {r['issue']}: {r['fix']}" for r in manual_fixes) or "- None"
            pdf_download_button(
                f"Migration Report — {job_name}",
                [
                    ("Cloud Readiness", f"Complexity Status: {level}\n"
                                         f"Migration Effort: {effort_hours}h\n"
                                         f"{_fix_summary.capitalize()}."),
                    ("Auto Fixes", _auto_fix_text),
                    ("Manual Fixes", _manual_fix_text),
                ],
                key=f"migration_pdf_{job_name}",
                file_name=f"{job_name}_migration.pdf",
            )

            _jira_priority = {"CRITICAL": "Highest", "HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}
            jira_df = pd.DataFrame([
                {
                    "Summary": f"[{job_name}] {r['issue']}",
                    "Issue Type": "Task" if r["auto_fix"] else "Story",
                    "Priority": _jira_priority.get(str(r.get("risk", "")).upper(), "Medium"),
                    "Description": f"Impact: {r.get('impact', '—')}\nFix: {r.get('fix', '—')}\nEffort: {r.get('effort', '—')}",
                    "Labels": "auto-fix" if r["auto_fix"] else "manual-fix",
                }
                for r in job_recs
            ])
            st.download_button(
                "Export Jira CSV",
                data=jira_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{job_name}_jira_import.csv",
                mime="text/csv",
                key=f"jira_csv_{job_name}",
            )

            _ado_severity = {"CRITICAL": "1 - Critical", "HIGH": "2 - High", "MEDIUM": "3 - Medium", "LOW": "4 - Low"}
            ado_df = pd.DataFrame([
                {
                    "Title": f"[{job_name}] {r['issue']}",
                    "Work Item Type": "Task" if r["auto_fix"] else "User Story",
                    "Severity": _ado_severity.get(str(r.get("risk", "")).upper(), "3 - Medium"),
                    "Description": f"Impact: {r.get('impact', '—')}\nFix: {r.get('fix', '—')}\nEffort: {r.get('effort', '—')}",
                    "Tags": "auto-fix" if r["auto_fix"] else "manual-fix",
                }
                for r in job_recs
            ])
            st.download_button(
                "Export Azure DevOps CSV",
                data=ado_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{job_name}_azuredevops_import.csv",
                mime="text/csv",
                key=f"ado_csv_{job_name}",
            )

            # ── Upgrade Path ─────────────────────────────────────────────────────
            st.markdown("#### 🛤️ Upgrade Path")

            from app.api.migration_api import get_upgrade_path_result

            _up_source = jd.get("source_version") or jd.get("talend_version") or "Talend 7"
            _up_target = "Talend 8"
            _up_result = get_upgrade_path_result(jd, _up_source, _up_target)

            _up_status = _up_result.get("compatibilityStatus", "NotCompatible")
            _up_badge = {
                "Compatible": ("✅", "#d4edda", "#155724"),
                "Conditional": ("⚠️", "#fff3cd", "#856404"),
                "NotCompatible": ("⛔", "#f8d7da", "#721c24"),
            }.get(_up_status, ("⛔", "#f8d7da", "#721c24"))

            col_up1, col_up2, col_up3 = st.columns(3)
            with col_up1:
                st.markdown(f"**Source Version**  \n{_up_result.get('sourceVersion', '—')}")
            with col_up2:
                st.markdown(f"**Target Version**  \n{_up_result.get('targetVersion', '—')}")
            with col_up3:
                st.markdown(
                    f"**Compatibility Status**  \n"
                    f"<span style='background:{_up_badge[1]};color:{_up_badge[2]};"
                    f"padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700;'>"
                    f"{_up_badge[0]} {_up_status}</span>",
                    unsafe_allow_html=True,
                )

            _up_targets = _up_result.get("targetVersions", [])
            if _up_targets:
                st.markdown(f"**Supported Target Versions:** {', '.join(_up_targets)}")
            else:
                st.markdown("**Supported Target Versions:** _none available_")

            _up_path = _up_result.get("migrationPath", [])
            if _up_path:
                st.markdown(f"**Migration Path:** {' → '.join(_up_path)}")

            _up_warnings = _up_result.get("warnings", [])
            if _up_warnings:
                st.markdown("**Warnings**")
                for w in _up_warnings:
                    _sev_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡"}.get(w.get("severity", "MEDIUM"), "🟠")
                    st.markdown(f"- {_sev_icon} `{w.get('component')}` ({w.get('category')}): {w.get('message')}")
            else:
                st.markdown("**Warnings:** _none_")

            _up_blockers = _up_result.get("blockers", [])
            if _up_blockers:
                st.markdown("**Blockers**")
                for b in _up_blockers:
                    st.markdown(f"- 🚫 {b}")
            else:
                st.markdown("**Blockers:** _none_")

        with _em_valid:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_validation"
            from app.ui.tdd_page import _render_validation
            _render_validation()

        with _em_cop:
            st.markdown("#### 🤖 AI Copilot")
            st.caption(f"Ask questions about **{job_name}** — sourced from actual job analysis data.")

            # ── Build rich data-driven answers from real job objects ──────────────
            _cp_inv       = _inv
            _cp_sources   = [s.get("name", "") for s in _cp_inv.get("sources", []) if s.get("name")]
            _cp_targets   = [t.get("name", "") for t in _cp_inv.get("targets", []) if t.get("name")]
            _cp_sql_ops   = _sql_ops
            _cp_comps     = jd.get("components", [])
            _cp_comp_types = sorted({c.get("component_type", "") for c in _cp_comps if c.get("component_type")})
            _cp_risks     = job.get("enterprise_risk_report", [])
            _cp_complexity = job.get("complexity", {})
            _cp_cx_level  = _cp_complexity.get("complexity", _cp_complexity.get("level", "—"))
            _cp_cx_score  = _cp_complexity.get("score", "—")
            _cp_cloud     = job.get("cloud_readiness", {})
            _cp_deps      = job.get("dependencies", {})
            _cp_child_jobs = []
            for _c in _cp_comps:
                if _c.get("component_type") == "tRunJob":
                    _p = component_parameters(_c)
                    _cj = normalize_name(
                        _p.get("PROCESS") or _p.get("JOB_NAME") or _p.get("CHILD_JOB") or
                        _p.get("PROCESS_NAME") or _p.get("SUBPROCESS")
                    )
                    if _cj:
                        _cp_child_jobs.append(_cj)
            _cp_parent_jobs = [
                j["job_data"]["job_name"] for j in all_jobs
                if j["job_data"]["job_name"] != job_name
                and any(
                    normalize_name(
                        component_parameters(c).get("PROCESS") or
                        component_parameters(c).get("JOB_NAME") or ""
                    ) == job_name
                    for c in j["job_data"].get("components", [])
                    if c.get("component_type") == "tRunJob"
                )
            ]
            _cp_routine_usage: dict[str, int] = {}
            for _c in _cp_comps:
                for _v in (_c.get("parameters") or {}).values():
                    for _rn in re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", str(_v)):
                        _cp_routine_usage[_rn] = _cp_routine_usage.get(_rn, 0) + 1
            _cp_java_comps = [c for c in _cp_comps if c.get("component_type") in {"tJava", "tJavaRow", "tJavaFlex"}]

            def _copilot_answer(question: str, free_text: str = "") -> str:  # noqa: C901
                q = (free_text or question).lower()

                # ── "What does this job do?" ───────────────────────────────────────
                if question == "overview" or any(w in q for w in ("what does", "what is this job", "job do", "purpose", "overview", "describe")):
                    parts = [f"**{job_name}** is a Talend ETL job"]
                    if _cp_sources and _cp_targets:
                        parts.append(f"that reads from **{', '.join(_cp_sources)}** and writes to **{', '.join(_cp_targets)}**.")
                    elif _cp_sources:
                        parts.append(f"that reads data from **{', '.join(_cp_sources)}**.")
                    elif _cp_targets:
                        parts.append(f"that produces output for **{', '.join(_cp_targets)}**.")
                    else:
                        parts.append("with no explicitly identified external sources or targets.")

                    parts.append(f"\n\n**Components ({len(_cp_comps)} total):** {', '.join(_cp_comp_types[:10]) or 'None'}")

                    if _cp_sql_ops:
                        tables = sorted({
                            t for op in _cp_sql_ops
                            for t in re.findall(r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([A-Za-z0-9_.\"]+)", op.get("query",""), re.IGNORECASE)
                        })
                        parts.append(f"\n\n**SQL operations:** {len(_cp_sql_ops)} quer{'y' if len(_cp_sql_ops)==1 else 'ies'}"
                                     + (f" touching tables: {', '.join(tables[:6])}" if tables else ""))

                    if _cp_java_comps:
                        parts.append(f"\n\n**Custom Java:** {len(_cp_java_comps)} Java component(s) ({', '.join(c.get('component_type','') for c in _cp_java_comps)}).")

                    if _cp_routine_usage:
                        parts.append(f"\n\n**Routines used:** {', '.join(sorted(_cp_routine_usage)[:8])}")

                    parts.append(f"\n\n**Complexity Status:** {_cp_cx_level}  |  "
                                 f"**Cloud Readiness:** {_cp_cloud.get('rag', _score_to_rag(_cp_cloud.get('score', 0)))}"),
                    return "".join(parts)

                # ── "Migration risk?" ─────────────────────────────────────────────
                if question == "risk" or any(w in q for w in ("risk", "migration risk", "problem", "issue", "blocker", "concern", "critical", "high risk")):
                    if not _cp_risks:
                        return (
                            f"**Migration Risk for {job_name}:** No high-risk findings were recorded.\n\n"
                            f"Complexity status is **{_cp_cx_level}**. "
                            f"Cloud Readiness: **{_cp_cloud.get('rag', _score_to_rag(_cp_cloud.get('score', 0)))}**.\n\n"
                            "Standard migration path should apply — verify job execution after import."
                        )
                    _by_level = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
                    for r in _cp_risks:
                        _by_level.get(r.get("risk", "LOW"), _by_level["LOW"]).append(r)
                    lines = [f"**Migration Risk Report — {job_name}**\n"]
                    for lvl in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                        _icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}[lvl]
                        for r in _by_level[lvl]:
                            comp = r.get("component", "Unknown component")
                            msg  = r.get("message", "")
                            lines.append(f"{_icon} **{lvl}** — `{comp}`: {msg}")
                    lines.append(f"\n**Complexity Status:** {_cp_cx_level}  |  **Cloud Readiness:** {_cp_cloud.get('rag', _score_to_rag(_cp_cloud.get('score', 0)))}")
                    if _cp_java_comps:
                        lines.append(f"\n⚠️ {len(_cp_java_comps)} custom Java component(s) require manual review before migration.")
                    return "\n".join(lines)

                # ── "Dependencies?" ───────────────────────────────────────────────
                if question == "dependencies" or any(w in q for w in ("depend", "child job", "parent job", "calls", "routine", "joblet", "upstream", "downstream")):
                    lines = [f"**Dependencies for {job_name}**\n"]
                    lines.append(f"**Parent jobs (upstream):** {', '.join(_cp_parent_jobs) if _cp_parent_jobs else 'None — this job is not called by any other job in the repository.'}")
                    lines.append(f"\n**Child jobs (downstream):** {', '.join(_cp_child_jobs) if _cp_child_jobs else 'None — this job does not call other jobs.'}")
                    if _cp_routine_usage:
                        lines.append(f"\n**Custom routines used:** {', '.join(f'{k} (×{v})' for k,v in sorted(_cp_routine_usage.items(), key=lambda x:-x[1])[:10])}")
                    else:
                        lines.append("\n**Custom routines:** None detected.")
                    contexts = jd.get("contexts", [])
                    ctx_names = [c.get("name") for c in contexts if isinstance(c, dict) and c.get("name")]
                    if ctx_names:
                        lines.append(f"\n**Context variables:** {', '.join(ctx_names[:10])}")
                    meta_items = _cp_inv.get("sources", []) + _cp_inv.get("targets", [])
                    if meta_items:
                        conn_names = sorted({m.get("component","") for m in meta_items if m.get("component")})
                        lines.append(f"\n**Metadata connections:** {', '.join(conn_names[:8])}")
                    return "\n".join(lines)

                # ── "SQL summary?" ────────────────────────────────────────────────
                if question == "sql" or any(w in q for w in ("sql", "query", "queries", "database", "table", "select", "insert", "update", "delete", "join")):
                    if not _cp_sql_ops:
                        return f"**SQL Summary for {job_name}:** No SQL operations detected in this job's components."
                    all_tables: set[str] = set()
                    lines = [f"**SQL Summary — {job_name}** ({len(_cp_sql_ops)} quer{'y' if len(_cp_sql_ops)==1 else 'ies'})\n"]
                    for i, op in enumerate(_cp_sql_ops, 1):
                        q_text = op.get("query", "").strip()
                        tables = re.findall(r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([A-Za-z0-9_.\"]+)", q_text, re.IGNORECASE)
                        for t in tables:
                            all_tables.add(t.strip('"'))
                        qtype = "SELECT" if q_text.upper().startswith("SELECT") else \
                                "INSERT" if q_text.upper().startswith("INSERT") else \
                                "UPDATE" if q_text.upper().startswith("UPDATE") else \
                                "DELETE" if q_text.upper().startswith("DELETE") else "SQL"
                        lines.append(f"**Query {i}** ({op.get('component','?')} / {op.get('db_type','?')}): `{qtype}` touching {', '.join(tables) if tables else 'unknown tables'}")
                    if all_tables:
                        lines.append(f"\n**All tables referenced:** {', '.join(sorted(all_tables))}")
                    return "\n".join(lines)

                # ── "Components?" ─────────────────────────────────────────────────
                if any(w in q for w in ("component", "step", "how many", "list of")):
                    counts: dict[str, int] = {}
                    for c in _cp_comps:
                        ct = c.get("component_type", "Unknown")
                        counts[ct] = counts.get(ct, 0) + 1
                    lines = [f"**Components in {job_name}** ({len(_cp_comps)} total)\n"]
                    for ct, cnt in sorted(counts.items(), key=lambda x: -x[1]):
                        lines.append(f"- `{ct}`: {cnt}")
                    return "\n".join(lines)

                # ── "Complexity?" ─────────────────────────────────────────────────
                if any(w in q for w in ("complex", "score", "effort", "hours", "estimate")):
                    rf = _cp_complexity.get("risk_factors", [])
                    return (
                        f"**Complexity — {job_name}**\n\n"
                        f"- Status: **{_cp_cx_level}**\n"
                        f"- Components: {len(_cp_comps)}\n"
                        f"- SQL queries: {len(_cp_sql_ops)}\n"
                        f"- Custom Java: {len(_cp_java_comps)}\n"
                        f"- Risk factors: {', '.join(rf) if rf else 'None'}\n"
                        f"- Cloud Readiness: {_cp_cloud.get('rag', _score_to_rag(_cp_cloud.get('score', 0)))}\n"
                        f"- Estimated effort: {job.get('estimation', {}).get('hours', '—')}h"
                    )

                # ── "Java?" ───────────────────────────────────────────────────────
                if any(w in q for w in ("java", "tjava", "inline", "custom code")):
                    if not _cp_java_comps:
                        return f"**Java Logic — {job_name}:** No tJava / tJavaRow / tJavaFlex components detected in this job."
                    lines = [f"**Java Logic — {job_name}** ({len(_cp_java_comps)} component(s))\n"]
                    for c in _cp_java_comps:
                        lines.append(f"- `{c.get('component_type')}` ({c.get('unique_name','?')})")
                    lines.append("\n⚠️ Custom Java requires manual review before migration to Talend Cloud.")
                    return "\n".join(lines)

                # ── Free-text fallback: return the most relevant answer ───────────
                # Try to match any keyword and return best fit
                if any(w in q for w in ("source", "input", "read", "ingest")):
                    return f"**Sources for {job_name}:** {', '.join(_cp_sources) if _cp_sources else 'None detected.'}"
                if any(w in q for w in ("target", "output", "write", "destination", "sink")):
                    return f"**Targets for {job_name}:** {', '.join(_cp_targets) if _cp_targets else 'None detected.'}"

                # Generic fallback with job summary
                return (
                    f"I don't have a specific answer for that, but here's a summary of **{job_name}**:\n\n"
                    f"- **Sources:** {', '.join(_cp_sources) or 'None detected'}\n"
                    f"- **Targets:** {', '.join(_cp_targets) or 'None detected'}\n"
                    f"- **Components:** {len(_cp_comps)} ({', '.join(_cp_comp_types[:5])})\n"
                    f"- **SQL queries:** {len(_cp_sql_ops)}\n"
                    f"- **Complexity Status:** {_cp_cx_level}\n"
                    f"- **Risk findings:** {len(_cp_risks)}\n\n"
                    "Try asking: *What does this job do? / Migration risk? / Dependencies? / SQL summary? / Java? / Components?*"
                )

            copilot_history = st.session_state.setdefault(f"copilot_history_{job_name}", [])

            _qmap = {
                f"copilot_suggest_overview_{job_name}":  ("What does this job do?", "overview"),
                f"copilot_suggest_risk_{job_name}":      ("Migration risk?",        "risk"),
                f"copilot_suggest_deps_{job_name}":      ("Dependencies?",          "dependencies"),
                f"copilot_suggest_sql_{job_name}":       ("SQL summary?",           "sql"),
            }

            if not copilot_history:
                st.info("No conversation yet. Click a suggested prompt or type a question below.")
            else:
                for _msg in copilot_history:
                    with st.chat_message(_msg.get("role", "assistant")):
                        st.markdown(_msg.get("content", ""))

            _chat_q = st.chat_input(
                f"Ask about {job_name} — sources, targets, SQL, risk, Java, complexity…",
                key=f"copilot_input_{job_name}",
            )
            if _chat_q:
                copilot_history.append({"role": "user", "content": _chat_q})
                copilot_history.append({"role": "assistant", "content": _copilot_answer("free", free_text=_chat_q)})
                st.rerun()

            st.markdown("##### Suggested Prompts")
            sc1, sc2, sc3, sc4 = st.columns(4)
            for _col, _key in zip((sc1, sc2, sc3, sc4), _qmap):
                with _col:
                    _label, _qtype = _qmap[_key]
                    if st.button(_label, key=_key, width="stretch"):
                        copilot_history.append({"role": "user", "content": _label})
                        copilot_history.append({"role": "assistant", "content": _copilot_answer(_qtype)})
                        st.rerun()

            if copilot_history:
                st.markdown("---")
                if st.button("Clear conversation", key=f"copilot_clear_{job_name}"):
                    st.session_state[f"copilot_history_{job_name}"] = []
                    st.rerun()

        with _em_mig:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_migration_assessment"
            from app.ui.tdd_page import _render_migration_assessment_section
            _render_migration_assessment_section()

        # ── Column Mapping Tab ────────────────────────────────────────────────────

    if _cat_sel == "Architecture":
        # Compute joblets/routine_usage here in case Overview tab was never visited
        joblets = []
        seen_joblets: set = set()
        child_jobs = []
        routine_usage: dict[str, int] = {}
        for _c in jd.get("components", []):
            _ctype = _c.get("component_type", "")
            if _ctype.lower().startswith("tjoblet") or _ctype == "tJoblet":
                _params = component_parameters(_c)
                _jn = normalize_name(_params.get("JOBLET") or _params.get("PROCESS") or _c.get("unique_name") or _ctype)
                if _jn and _jn not in seen_joblets:
                    seen_joblets.add(_jn)
                    joblets.append(_jn)
            if _ctype == "tRunJob":
                _params = component_parameters(_c)
                _cj = normalize_name(
                    _params.get("PROCESS") or _params.get("JOB_NAME") or _params.get("CHILD_JOB")
                    or _params.get("PROCESS_NAME") or _params.get("SUBPROCESS")
                )
                if _cj:
                    child_jobs.append(_cj)
            for _value in (_c.get("parameters") or {}).values():
                for _rname in re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", str(_value)):
                    routine_usage[_rname] = routine_usage.get(_rname, 0) + 1

        _ar_flow, _ar_df, _ar_dep, _ar_job_arch, _ar_src, _ar_tgt, _ar_trf, _ar_job_flow = st.tabs(["Flowcharts", "Data Flow", "Dependencies", "Job Architecture", "Source Architecture", "Target Architecture", "Transformation Architecture", "Job Flow Architecture"])
        with _ar_flow:
            st.markdown(
                """
                <style>
                .tma-fc-wrap{display:flex;flex-wrap:wrap;align-items:center;gap:14px;}
                .tma-fc-step{background:#faf9f7;border:1px solid #e4e3dc;border-radius:16px;
                    padding:16px 18px 14px;min-width:150px;max-width:200px;}
                .tma-fc-step .num{font-size:10px;font-weight:600;color:#b0aea8;letter-spacing:.05em;margin-bottom:10px;}
                .tma-fc-step .sicon{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:18px;margin-bottom:8px;background:#F5F4FE;color:#534AB7;}
                .tma-fc-step .ftitle{font-size:12px;font-weight:600;color:#1a1a18;margin-bottom:6px;}
                .tma-fc-step .fdet{font-size:11px;color:#6b6b66;line-height:1.6;
                    word-break:break-word;}
                .tma-fc-arrow{font-size:16px;color:#b0aea8;}
                </style>
                """,
                unsafe_allow_html=True,
            )

            flow_steps = _flow_steps
            st.markdown('<div class="tma-sec-label">Visual job flow — full component sequence</div>', unsafe_allow_html=True)

            _fc_components = [
                c for c in jd.get("components", [])
                if c.get("component_type", "Unknown") not in _SKIP_FLOW_COMPONENTS
            ]

            fc_html = '<div class="tma-fc-wrap">'
            step_idx = 0
            prev_fc_key = None
            for c in _fc_components:
                ctype = c.get("component_type", "Unknown")
                detail = _step_detail(c)
                key = (ctype, detail)
                if key == prev_fc_key:
                    continue
                prev_fc_key = key
                if step_idx >= len(flow_steps):
                    break
                icon, title, _ = flow_steps[step_idx]
                step_idx += 1
                if step_idx > 1:
                    fc_html += '<span class="tma-fc-arrow">&#8594;</span>'
                fc_html += (
                    f'<div class="tma-fc-step"><div class="num">{step_idx}</div><div class="sicon">{icon}</div>'
                    f'<div class="ftitle">{title}</div>'
                    f'<div class="fdet">{detail}</div></div>'
                )
            fc_html += '</div>'
            st.markdown(fc_html, unsafe_allow_html=True)

            st.markdown('<div class="tma-sec-label">Technical component sequence</div>', unsafe_allow_html=True)
            for c in jd.get("components", []):
                st.markdown(f"- {c.get('component_type', 'Unknown')} ({c.get('unique_name', '—')})")

        with _ar_job_arch:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_job_arch"
            from app.ui.tdd_page import _render_architecture
            _render_architecture()

        with _ar_src:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_source_arch"
            from app.ui.tdd_page import _render_source_architecture
            _render_source_architecture()

        with _ar_tgt:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_target_arch"
            from app.ui.tdd_page import _render_target_architecture
            _render_target_architecture()

        with _ar_trf:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_transform_arch"
            from app.ui.tdd_page import _render_transformation_architecture
            _render_transformation_architecture()

        with _ar_job_flow:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_job_flow_arch"
            from app.ui.tdd_page import _render_job_flow_architecture
            _render_job_flow_architecture()

        with _ar_df:
            st.markdown("### Data Flow")

            _df_inv = _inv
            _df_sources = [s.get("name", "") for s in _df_inv.get("sources", []) if s.get("name")]
            _df_targets = [t.get("name", "") for t in _df_inv.get("targets", []) if t.get("name")]

            TRANSFORM_TYPES_DF = {"tMap", "tJoin", "tSortRow", "tAggregateRow", "tNormalize", "tConvertType", "tReplace", "tFilterRow"}
            _df_transforms = [
                {"name": c.get("unique_name", c.get("component_type", "Transform")), "type": c.get("component_type", "")}
                for c in jd.get("components", [])
                if c.get("component_type") in TRANSFORM_TYPES_DF
            ]

            st.markdown(
                """
                <style>
                .df-section-title{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
                    color:#8a8a85;margin:18px 0 10px;}
                .df-card{background:#fff;border:1px solid #e4e3dc;border-radius:10px;padding:12px 16px;
                    margin-bottom:8px;display:flex;align-items:flex-start;gap:10px;}
                .df-card-icon{font-size:20px;line-height:1;margin-top:2px;}
                .df-card-body{}
                .df-card-name{font-size:13px;font-weight:600;color:#1a1a18;}
                .df-card-sub{font-size:11px;color:#6b6b66;margin-top:2px;}
                .df-arrow-row{display:flex;align-items:center;justify-content:center;
                    font-size:22px;color:#b0aea8;margin:6px 0;}
                .df-empty{font-size:13px;color:#9e9e96;font-style:italic;}
                .df-flow-wrap{display:flex;flex-direction:column;gap:4px;}
                </style>
                """,
                unsafe_allow_html=True,
            )

            col_src, col_mid, col_trf, col_mid2, col_tgt = st.columns([3, 1, 3, 1, 3])

            with col_src:
                st.markdown('<div class="df-section-title">📥 Source Tables</div>', unsafe_allow_html=True)
                if _df_sources:
                    for src in _df_sources:
                        st.markdown(
                            f'<div class="df-card"><div class="df-card-icon">🗄️</div>'
                            f'<div class="df-card-body"><div class="df-card-name">{html_lib.escape(src)}</div>'
                            f'<div class="df-card-sub">Input table / file</div></div></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown('<div class="df-empty">No source tables detected</div>', unsafe_allow_html=True)

            with col_mid:
                st.markdown('<div style="height:56px;"></div>', unsafe_allow_html=True)
                st.markdown('<div class="df-arrow-row">→</div>', unsafe_allow_html=True)

            with col_trf:
                st.markdown('<div class="df-section-title">⚙️ Transforms</div>', unsafe_allow_html=True)
                if _df_transforms:
                    for tr in _df_transforms:
                        type_label = tr["type"] if tr["type"] != tr["name"] else ""
                        st.markdown(
                            f'<div class="df-card"><div class="df-card-icon">⚙️</div>'
                            f'<div class="df-card-body"><div class="df-card-name">{html_lib.escape(tr["name"])}</div>'
                            f'<div class="df-card-sub">{html_lib.escape(type_label)}</div></div></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown('<div class="df-empty">No transform components detected</div>', unsafe_allow_html=True)

            with col_mid2:
                st.markdown('<div style="height:56px;"></div>', unsafe_allow_html=True)
                st.markdown('<div class="df-arrow-row">→</div>', unsafe_allow_html=True)

            with col_tgt:
                st.markdown('<div class="df-section-title">📤 Target Output</div>', unsafe_allow_html=True)
                if _df_targets:
                    for tgt in _df_targets:
                        st.markdown(
                            f'<div class="df-card"><div class="df-card-icon">🎯</div>'
                            f'<div class="df-card-body"><div class="df-card-name">{html_lib.escape(tgt)}</div>'
                            f'<div class="df-card-sub">Output table / file</div></div></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown('<div class="df-empty">No target outputs detected</div>', unsafe_allow_html=True)

            # ── Mermaid end-to-end flow diagram ─────────────────────────────────────
            st.markdown("---")
            st.markdown('<div class="df-section-title">End-to-End Data Flow Diagram</div>', unsafe_allow_html=True)

            def _df_node(name: str) -> str:
                return re.sub(r"[^A-Za-z0-9_]", "_", str(name))

            df_mermaid = ["graph LR"]
            for s in _df_sources:
                df_mermaid.append(f'    SRC_{_df_node(s)}[("📥 {s}")]')
            for tr in _df_transforms:
                df_mermaid.append(f'    TRF_{_df_node(tr["name"])}["⚙️ {tr["name"]}"]')
            for t in _df_targets:
                df_mermaid.append(f'    TGT_{_df_node(t)}[("📤 {t}")]')

            src_ids = [f'SRC_{_df_node(s)}' for s in _df_sources]
            trf_ids = [f'TRF_{_df_node(tr["name"])}' for tr in _df_transforms]
            tgt_ids = [f'TGT_{_df_node(t)}' for t in _df_targets]

            if src_ids and trf_ids:
                for s in src_ids:
                    for tr in trf_ids:
                        df_mermaid.append(f"    {s} --> {tr}")
            elif src_ids and tgt_ids:
                for s in src_ids:
                    for t in tgt_ids:
                        df_mermaid.append(f"    {s} --> {t}")

            if trf_ids and tgt_ids:
                for tr in trf_ids:
                    for t in tgt_ids:
                        df_mermaid.append(f"    {tr} --> {t}")
            elif not src_ids and trf_ids:
                for tr in trf_ids:
                    for t in tgt_ids:
                        df_mermaid.append(f"    {tr} --> {t}")

            if any([src_ids, trf_ids, tgt_ids]):
                _render_mermaid("\n".join(df_mermaid), height=380)
            else:
                st.info("No data flow components could be determined for this job.")

        with _ar_dep:
            st.markdown("#### Impact Analysis")

            downstream = []
            for c in jd.get("components", []):
                if c.get("component_type") != "tRunJob":
                    continue
                params = component_parameters(c)
                child = (
                    params.get("PROCESS")
                    or params.get("JOB_NAME")
                    or params.get("CHILD_JOB")
                    or params.get("PROCESS_NAME")
                    or params.get("SUBPROCESS")
                )
                child = normalize_name(child)
                if child:
                    downstream.append(child)

            upstream = []
            for j in all_jobs:
                other_jd = j["job_data"]
                other_name = other_jd.get("job_name", "—")
                if other_name == job_name:
                    continue
                for c in other_jd.get("components", []):
                    if c.get("component_type") != "tRunJob":
                        continue
                    params = component_parameters(c)
                    ref = (
                        params.get("PROCESS")
                        or params.get("JOB_NAME")
                        or params.get("CHILD_JOB")
                        or params.get("PROCESS_NAME")
                        or params.get("SUBPROCESS")
                    )
                    ref = normalize_name(ref)
                    if ref == job_name:
                        upstream.append(other_name)

            st.markdown("**Upstream**")
            if upstream:
                for u in upstream:
                    st.markdown(f"- {u}")
            else:
                st.markdown("- None")

            st.markdown("**Downstream**")
            if downstream:
                for d in downstream:
                    st.markdown(f"- {d}")
            else:
                st.markdown("- None")

            st.markdown("#### Dependency Graph")
            if upstream or downstream:
                _complexity_by_job = {
                    j["job_data"].get("job_name"): j.get("complexity", {}).get("complexity", "LOW")
                    for j in all_jobs
                }
                _risk_class = {"LOW": "riskLow", "MEDIUM": "riskMedium", "HIGH": "riskHigh", "CRITICAL": "riskCritical"}

                def _node_id(name: str) -> str:
                    return re.sub(r"[^A-Za-z0-9_]", "_", str(name))

                def _node_risk_class(name: str) -> str:
                    return _risk_class.get(_complexity_by_job.get(name, "LOW"), "riskLow")

                dep_mermaid = ["graph LR"]
                this_id = _node_id(job_name)
                dep_mermaid.append(f'    {this_id}["{job_name}"]')
                dep_mermaid.append(f'    class {this_id} {_node_risk_class(job_name)}')
                for u in upstream:
                    u_id = _node_id(u)
                    dep_mermaid.append(f'    {u_id}["{u}"] --> {this_id}')
                    dep_mermaid.append(f'    class {u_id} {_node_risk_class(u)}')
                for d in downstream:
                    d_id = _node_id(d)
                    dep_mermaid.append(f'    {this_id} --> {d_id}["{d}"]')
                    dep_mermaid.append(f'    class {d_id} {_node_risk_class(d)}')
                dep_mermaid.append('    classDef riskLow fill:#f0fdf4,stroke:#38a169,color:#15803d;')
                dep_mermaid.append('    classDef riskMedium fill:#fefce8,stroke:#d69e2e,color:#b45309;')
                dep_mermaid.append('    classDef riskHigh fill:#fff1f2,stroke:#e53e3e,color:#be123c;')
                dep_mermaid.append('    classDef riskCritical fill:#fff1f2,stroke:#e53e3e,color:#be123c;')
                _render_mermaid("\n".join(dep_mermaid), height=320)
            else:
                st.markdown("- No dependencies found.")

            st.markdown("#### Metadata Dependencies")
            meta_inv = _inv
            meta_items = meta_inv.get("sources", []) + meta_inv.get("targets", [])

            if meta_items:
                for item in meta_items:
                    conn = item.get("component", "—")
                    schema = item.get("name", "—")
                    st.markdown(f"- **Connection:** {conn} — **Schema:** {schema}")
            else:
                st.markdown("- None")

            st.markdown("#### Context Dependencies")
            contexts = jd.get("contexts", [])
            context_vars = [c for c in contexts if isinstance(c, dict) and c.get("name")]

            if context_vars:
                groups = {}
                for cv in context_vars:
                    group = cv.get("group", "Default")
                    groups.setdefault(group, []).append(cv)

                for group, vars_ in groups.items():
                    st.markdown(f"**{group}**")
                    for cv in vars_:
                        name = cv.get("name", "—")
                        value = cv.get("value", "—")
                        st.markdown(f"- `{name}`: {value}")
            else:
                st.markdown("- None")

            st.markdown("#### Dependency Summary")
            _context_groups_count = len(groups) if context_vars else 0
            st.markdown(
                f'''<div class="tma-cgrid">
                  <div class="tma-card"><div class="ci">Child Jobs</div><div class="cv">{len(downstream)}</div><div class="cs">child job(s) called</div></div>
                  <div class="tma-card"><div class="ci">Joblets</div><div class="cv">{len(joblets)}</div><div class="cs">joblet(s) used</div></div>
                  <div class="tma-card"><div class="ci">Routines</div><div class="cv">{len(routine_usage)}</div><div class="cs">routine(s) used</div></div>
                  <div class="tma-card"><div class="ci">Context Groups</div><div class="cv">{_context_groups_count}</div><div class="cs">context group(s)</div></div>
                </div>''',
                unsafe_allow_html=True,
            )


    if _cat_sel == "Mapping & Lineage":
        _ml_colmap, _ml_stt, _ml_column_lineage, _ml_lin = st.tabs(["Column Mapping", "Source-To-Target Mapping", "Column Lineage", "Lineage"])
        with _ml_colmap:
            render_column_mapping_tab(job, jd, _inv, all_jobs, job_name)

        with _ml_stt:
            st.markdown("#### Source-To-Target Mapping")
            _stt_sources = _inv.get("sources", [])
            _stt_targets = _inv.get("targets", [])
            _stt_rows = []
            for src in _stt_sources or [{"name": "Source not detected", "component": "—"}]:
                for tgt in _stt_targets or [{"name": "Target not detected", "component": "—"}]:
                    _stt_rows.append({
                        "Source": src.get("name", "—"),
                        "Source Component": src.get("component", "—"),
                        "Target": tgt.get("name", "—"),
                        "Target Component": tgt.get("component", "—"),
                    })
            st.dataframe(pd.DataFrame(_stt_rows), use_container_width=True, hide_index=True)

        with _ml_column_lineage:
            render_cached_lineage_page(preferred_job_name=job_name, default_view="Column Lineage", widget_key="_cached_lineage_col_lineage")

        # ── Lineage Tab ────────────────────────────────────────────────────────────
        with _ml_lin:
            render_cached_lineage_page(preferred_job_name=job_name, default_view="Job Lineage", widget_key="_cached_lineage_job_lineage")

        # ── TDD Tab ────────────────────────────────────────────────────────────────

    if _cat_sel == "Technical Analysis":
        _ta_sql, _ta_java, _ta_error, _ta_audit, _ta_perf, _ta_security = st.tabs(["SQL", "Java Logic", "Error Handling", "Audit", "Performance", "Security"])
        with _ta_error:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_error_handling"
            from app.ui.tdd_page import _render_error_handling
            _render_error_handling()

        with _ta_audit:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_audit"
            from app.ui.tdd_page import _render_audit_monitoring
            _render_audit_monitoring()

        with _ta_perf:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_performance"
            from app.ui.tdd_page import _render_performance
            _render_performance()

        with _ta_security:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_security"
            from app.ui.tdd_page import _render_security
            _render_security()

        with _ta_sql:
            # ── Tab-level styles (injected once) ─────────────────────────────────
            st.markdown(
                """
                <style>
                .cx-badge-LOW  {display:inline-block;padding:3px 12px;border-radius:20px;
                    font-size:12px;font-weight:700;background:#d4edda;color:#155724;}
                .cx-badge-MEDIUM{display:inline-block;padding:3px 12px;border-radius:20px;
                    font-size:12px;font-weight:700;background:#fff3cd;color:#856404;}
                .cx-badge-HIGH {display:inline-block;padding:3px 12px;border-radius:20px;
                    font-size:12px;font-weight:700;background:#f8d7da;color:#721c24;}
                .sql-exp-row  {display:grid;grid-template-columns:1fr 1.4fr;gap:0;
                    border-bottom:1px solid #f0efea;padding:6px 0;align-items:start;}
                .sql-exp-code {font-family:monospace;font-size:11px;color:#5a5a56;
                    background:#f7f6f1;border-radius:4px;padding:3px 6px;word-break:break-all;}
                .sql-exp-text {font-size:12px;color:#1a1a18;padding-left:12px;line-height:1.5;}
                .sql-exp-hdr  {font-size:11px;font-weight:700;letter-spacing:.06em;
                    text-transform:uppercase;color:#8a8a85;padding:4px 0 8px;}
                </style>
                """,
                unsafe_allow_html=True,
            )

            # ── Prepare data ──────────────────────────────────────────────────────
            sql_ops = _sql_ops
            sql_payload = tuple(
                (
                    op.get("component", ""),
                    op.get("db_type", ""),
                    _clean_sql(op.get("query", "")),
                )
                for op in sql_ops
                if _clean_sql(op.get("query", ""))
            )
            query_signature = hashlib.sha1(repr(sql_payload).encode("utf-8")).hexdigest()
            sql_context = _generate_sql_business_context(job_name, query_signature, sql_payload)

            n_queries  = len(sql_context["queries"])
            flow       = sql_context["flow"]
            all_src    = flow["sources"]
            all_tgt    = flow["targets"]
            transforms = flow["transformation"]

            # ── Job-level summary paragraph ───────────────────────────────────────
            st.markdown("### 📊 SQL Overview")
            if n_queries == 0:
                st.info(
                    f"**{job_name}** contains no executable SQL queries. "
                    "It may rely entirely on component-level configuration, file I/O, or Java logic."
                )
            else:
                q_word      = "query" if n_queries == 1 else "queries"
                src_text    = ", ".join(f"`{t}`" for t in all_src) if all_src else "an unresolved source"
                tgt_text    = ", ".join(f"`{t}`" for t in all_tgt) if all_tgt else "an unresolved target"
                tx_text     = (
                    " Transformations applied: " + ", ".join(t.lower() for t in transforms) + "."
                    if transforms and transforms != ["SQL execution logic"] else ""
                )
                qtype_text  = " and ".join(sorted({a["query_type"] for a in sql_context["queries"]}))
                st.markdown(
                    f"**{job_name}** executes **{n_queries} SQL {q_word}** ({qtype_text}) "
                    f"reading from {src_text} and writing to {tgt_text}.{tx_text} "
                    f"Overall confidence: **{sql_context['confidence']}%**."
                )

            # Job-level metric row
            col_q, col_s, col_t, col_x = st.columns(4)
            col_q.metric("SQL Queries",      n_queries)
            col_s.metric("Source Tables",    len([t for t in all_src if t != "Detected SQL input"]))
            col_t.metric("Target Tables",    len([t for t in all_tgt if t != "Detected SQL output"]))
            col_x.metric("Transformations",  len([t for t in transforms if t != "SQL execution logic"]))

            st.divider()

            # ── Per-query breakdown ───────────────────────────────────────────────
            if n_queries > 1:
                st.markdown("### Per-Query Breakdown")

            for analysis in sql_context["queries"]:
                _label = (
                    f"Query {analysis['index']} · {analysis['query_type']} · {analysis['component']}"
                )
                with st.expander(_label, expanded=(n_queries == 1)):

                    _qcx_level = analysis.get("complexity_level", "LOW")
                    _qcx_score = analysis.get("complexity_score", 0)
                    _qtype     = analysis.get("query_type", "SQL")

                    # ── 1. Business Purpose ───────────────────────────────────
                    st.markdown("#### 🎯 Business Purpose")
                    st.info(analysis["business_purpose"])
                    st.markdown(
                        f"**Confidence:** {analysis['confidence']}%  |  "
                        f"**Query Type:** {_qtype}  |  "
                        f"**Complexity:** "
                        f"<span class=\"cx-badge-{_qcx_level}\">{_qcx_level}</span> "
                        f"(score: {_qcx_score})",
                        unsafe_allow_html=True,
                    )

                    # ── 2. Plain English Summary ──────────────────────────────
                    st.markdown("#### 💬 Plain English Summary")
                    st.success(_plain_english_summary(analysis))

                    st.divider()

                    # ── 3. Source Tables  /  4. Column Mapping ────────────────
                    st.markdown("#### 🗂️ Source & Target Tables")
                    _src_col, _tgt_col = st.columns(2)
                    with _src_col:
                        st.markdown("**Source Tables**")
                        if analysis["source_tables"]:
                            for tbl in analysis["source_tables"]:
                                st.markdown(f"- `{tbl}`")
                        else:
                            st.markdown("_None detected_")
                    with _tgt_col:
                        st.markdown("**Target Tables**")
                        if analysis["target_tables"]:
                            for tbl in analysis["target_tables"]:
                                st.markdown(f"- `{tbl}`")
                        else:
                            st.markdown("_None detected_")

                    # Column Mapping — derived from SELECT clause
                    _sql_upper = analysis["query"].upper()
                    _select_m  = re.search(
                        r"\bSELECT\b(.+?)\bFROM\b", analysis["query"], re.IGNORECASE | re.DOTALL
                    )
                    if _select_m:
                        _col_raw = _select_m.group(1).strip()
                        _cols    = [c.strip() for c in _col_raw.split(",") if c.strip() and c.strip() != "*"]
                        if _cols:
                            st.markdown("**Column Mapping** _(SELECT clause)_")
                            _cm_pairs = []
                            for c in _cols:
                                parts = re.split(r"\s+AS\s+", c, maxsplit=1, flags=re.IGNORECASE)
                                if len(parts) == 2:
                                    _cm_pairs.append((parts[0].strip(), parts[1].strip()))
                                else:
                                    _cm_pairs.append((c, c.split(".")[-1]))
                            _hc1, _hc2 = st.columns(2)
                            _hc1.markdown("**Source Expression**")
                            _hc2.markdown("**Output Column**")
                            for _src_expr, _out_col in _cm_pairs[:20]:
                                _cc1, _cc2 = st.columns(2)
                                _cc1.markdown(f"`{_src_expr}`")
                                _cc2.markdown(f"`{_out_col}`")
                            if len(_cm_pairs) > 20:
                                st.caption(f"… and {len(_cm_pairs) - 20} more columns")

                    st.divider()

                    # ── 5. Join Analysis ──────────────────────────────────────
                    st.markdown("#### 🔗 Join Analysis")
                    joins_detail = analysis.get("joins_detail", [])
                    if joins_detail:
                        _jh1, _jh2, _jh3 = st.columns([1, 2, 3])
                        _jh1.markdown("**Join Type**")
                        _jh2.markdown("**Tables**")
                        _jh3.markdown("**Condition**")
                        st.markdown(
                            "<hr style='margin:2px 0 6px 0;border-color:#e4e3dc;'>",
                            unsafe_allow_html=True,
                        )
                        for _jd in joins_detail:
                            _jc1, _jc2, _jc3 = st.columns([1, 2, 3])
                            _jc1.markdown(f"`{_jd['join_type']}`")
                            _jc2.markdown(f"`{_jd['tables']}`")
                            _jc3.markdown(f"`{_jd['condition']}`")
                    else:
                        st.markdown("_No joins detected in this query._")

                    st.divider()

                    # ── 6. Filters ────────────────────────────────────────────
                    st.markdown("#### 🔍 Filters")
                    _filters = analysis.get("filters", [])
                    if _filters:
                        for _f in _filters:
                            st.markdown(f"- `{_f}`")
                    else:
                        st.markdown("_No WHERE-clause filters detected._")

                    # ── 7. Business Rules ─────────────────────────────────────
                    st.markdown("#### 📋 Business Rules")
                    for rule in _business_rules_list(analysis):
                        st.markdown(f"- {rule}")

                    # Extracted conditional logic (CASE/IF/DECODE/NVL/COALESCE)
                    _bl = analysis.get("business_logic", {})
                    _bl_items = [
                        ("CASE WHEN", "🔀", _bl.get("case_when", [])),
                        ("IF",        "❓", _bl.get("if_expr",  [])),
                        ("DECODE",    "🔄", _bl.get("decode",   [])),
                        ("NVL",       "🛡️", _bl.get("nvl",      [])),
                        ("COALESCE",  "🔗", _bl.get("coalesce", [])),
                    ]
                    if any(exprs for _, _, exprs in _bl_items):
                        st.markdown("**Conditional Expressions**")
                        for _lbl, _icon, _exprs in _bl_items:
                            if _exprs:
                                with st.expander(
                                    f"{_icon} {_lbl} — {len(_exprs)} expression{'s' if len(_exprs) != 1 else ''}",
                                    expanded=False,
                                ):
                                    for _expr in _exprs:
                                        st.code(_expr, language="sql")

                    st.divider()

                    # ── 8. Aggregations ───────────────────────────────────────
                    st.markdown("#### Σ Aggregations")
                    _aggs  = analysis.get("aggregations", [])
                    _wfuncs = analysis.get("window_functions", [])
                    if _aggs or _wfuncs:
                        if _aggs:
                            st.markdown(f"**Aggregate functions:** {', '.join(f'`{a}`' for a in _aggs)}")
                        if _wfuncs:
                            st.markdown(f"**Window functions:** {', '.join(f'`{w}`' for w in _wfuncs)}")
                    else:
                        st.markdown("_No aggregation or window functions detected._")

                    # ── 9. Data Flow ──────────────────────────────────────────
                    st.markdown("#### 🔄 Data Flow")
                    _src_b = " → ".join(f"`{t}`" for t in analysis["source_tables"]) or "_unknown_"
                    _tgt_b = " → ".join(f"`{t}`" for t in analysis["target_tables"]) or "_unknown_"
                    _tx_b  = " · ".join(t for t in transforms if t != "SQL execution logic") or "—"
                    st.markdown(
                        f"**Source →** {_src_b}  \n"
                        f"**Transform →** {_tx_b}  \n"
                        f"**Target →** {_tgt_b}"
                    )
                    # Flag special data-handling patterns
                    _flags = []
                    if analysis.get("match_merge_logic"):
                        _flags.append("🔀 Match / Merge logic detected")
                    if analysis.get("deduplication_logic"):
                        _flags.append("♻️ Deduplication logic detected")
                    if analysis.get("surrogate_key_generation"):
                        _flags.append("🔑 Surrogate key generation detected")
                    if analysis.get("cdc_logic"):
                        _flags.append("📡 Change-Data-Capture (CDC) logic detected")
                    for _fl in _flags:
                        st.markdown(f"- {_fl}")

                    st.divider()

                    # ── 10. Complexity ────────────────────────────────────────
                    st.markdown("#### 🧮 Complexity")
                    _cx_c1, _cx_c2, _cx_c3, _cx_c4, _cx_c5 = st.columns(5)
                    _cx_c1.metric("Tables",     len(analysis["source_tables"]) + len(analysis["target_tables"]),
                                  help="Source + target tables")
                    _cx_c2.metric("Joins",      len(joins_detail),
                                  help="JOIN operations in this query")
                    _cx_c3.metric("Subqueries", analysis.get("subqueries", 0),
                                  help="Nested SELECT subqueries")
                    _cx_c4.metric("Functions",  len(analysis.get("sql_functions", [])),
                                  help="Distinct SQL functions used")
                    with _cx_c5:
                        st.markdown(
                            f'<div style="margin-top:8px;">'
                            f'<div style="font-size:11px;font-weight:700;letter-spacing:.07em;'
                            f'text-transform:uppercase;color:#8a8a85;margin-bottom:6px;">Level</div>'
                            f'<span class="cx-badge-{_qcx_level}">{_qcx_level}</span></div>',
                            unsafe_allow_html=True,
                        )
                    _all_sql_funcs = analysis.get("sql_functions", [])
                    if _all_sql_funcs:
                        st.markdown(f"**Functions used:** `{'` · `'.join(_all_sql_funcs)}`")

                    # ── 11. Migration Impact ──────────────────────────────────
                    st.markdown("#### 🚀 Migration Impact")
                    _mig_notes = []
                    if analysis.get("match_merge_logic"):
                        _mig_notes.append(
                            "**MERGE / UPSERT** — Talend Cloud uses `tMap` with reject flows or "
                            "`tDBUpsert`; verify the ON clause maps to a supported lookup key."
                        )
                    if analysis.get("cdc_logic"):
                        _mig_notes.append(
                            "**CDC columns** — map `UPDATED_AT`, `OP_TYPE`, or `DELETE_FLAG` fields "
                            "to Talend Cloud's built-in CDC components (`tKafkaInput`, `tDebeziumInput`)."
                        )
                    if analysis.get("surrogate_key_generation"):
                        _mig_notes.append(
                            "**Surrogate keys** — `SEQUENCE` / `NEXTVAL` must be replaced with "
                            "`tSequence` or database-native identity in Talend Cloud."
                        )
                    if any("PIVOT" in f or "UNPIVOT" in f for f in _all_sql_funcs):
                        _mig_notes.append(
                            "**PIVOT / UNPIVOT** — not natively supported in most Talend components; "
                            "rewrite using `tMap` with multiple output rows or a Java tidy step."
                        )
                    if analysis.get("window_functions"):
                        _mig_notes.append(
                            "**Window functions** — push-down to the database where possible; "
                            "otherwise use `tMap` + `tSortRow` + `tJavaRow` for in-memory equivalents."
                        )
                    if _qtype in ("UPDATE", "DELETE", "MERGE"):
                        _mig_notes.append(
                            f"**{_qtype} query** — Cloud pipelines prefer insert-based or "
                            "SCD patterns; confirm the target component supports direct DML."
                        )
                    if _mig_notes:
                        for _mn in _mig_notes:
                            st.markdown(f"- {_mn}")
                    else:
                        st.success("No specific migration risks identified for this query.")

                    st.divider()

                    # ── 12. Performance Notes ─────────────────────────────────
                    st.markdown("#### ⚡ Performance Notes")

                    _perf_sql     = analysis["query"]
                    _perf_upper   = _perf_sql.upper()
                    _perf_joins   = analysis.get("joins_detail", [])
                    _perf_filters = analysis.get("filters", [])
                    _perf_src     = analysis.get("source_tables", [])
                    _perf_notes   = []

                    _cross_join = any("CROSS" in j.get("join_type", "") for j in _perf_joins)
                    if len(_perf_joins) >= 3:
                        _perf_notes.append({
                            "flag": "🔴 Large Joins",
                            "detail": f"{len(_perf_joins)} join(s) — verify indexes on all join keys to avoid full-table scans.",
                            "severity": "high",
                        })
                    elif len(_perf_joins) >= 1:
                        _perf_notes.append({
                            "flag": "🟡 Join Present",
                            "detail": f"{len(_perf_joins)} join(s) — ensure join columns are indexed.",
                            "severity": "medium",
                        })

                    _has_cross       = _cross_join or bool(re.search(r"\bCROSS\s+JOIN\b", _perf_upper))
                    _join_without_on = any(not j.get("condition", "").strip() for j in _perf_joins) if _perf_joins else False
                    if _has_cross or _join_without_on:
                        _perf_notes.append({
                            "flag": "🔴 Cartesian Risk",
                            "detail": "CROSS JOIN or join without ON condition — may produce explosive row multiplication.",
                            "severity": "high",
                        })
                    elif len(_perf_src) >= 2 and not _perf_joins and not _perf_filters:
                        _perf_notes.append({
                            "flag": "🟡 Possible Cartesian",
                            "detail": "Multiple source tables with no explicit joins or filters — verify this is not an implicit cross join.",
                            "severity": "medium",
                        })

                    _has_where = bool(re.search(r"\bWHERE\b", _perf_upper))
                    if _qtype in ("SELECT", "UPDATE", "DELETE") and not _has_where:
                        _perf_notes.append({
                            "flag": "🔴 Missing Filters",
                            "detail": f"{_qtype} with no WHERE clause — full table scan likely; add predicate or partition pruning.",
                            "severity": "high",
                        })
                    elif _qtype == "SELECT" and _has_where and not _perf_filters:
                        _perf_notes.append({
                            "flag": "🟡 Weak Filters",
                            "detail": "WHERE present but no extractable filter conditions — verify selectivity.",
                            "severity": "medium",
                        })

                    _found_heavy = [
                        label for kw, label in _SQL_HEAVY_FUNCTIONS.items()
                        if re.search(r"\b" + kw + r"\b", _perf_upper)
                    ]
                    if _found_heavy:
                        _perf_notes.append({
                            "flag": "🔴 Heavy Functions",
                            "detail": f"Detected: {', '.join(_found_heavy)} — memory- and CPU-intensive; ensure partitioning or indexing support.",
                            "severity": "high",
                        })
                    if bool(re.search(r"\bDISTINCT\b", _perf_upper)):
                        _perf_notes.append({
                            "flag": "🟡 DISTINCT Usage",
                            "detail": "DISTINCT forces a full sort/hash deduplication pass — consider deduplicating upstream.",
                            "severity": "medium",
                        })
                    if analysis.get("subqueries", 0) >= 2:
                        _perf_notes.append({
                            "flag": "🟡 Nested Subqueries",
                            "detail": f"{analysis['subqueries']} subqueries — consider CTEs or temp tables to improve planner efficiency.",
                            "severity": "medium",
                        })

                    if _perf_notes:
                        _perf_notes.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 9))
                        for _pn in _perf_notes:
                            st.markdown(f"**{_pn['flag']}** — {_pn['detail']}")
                    else:
                        st.success("No significant performance concerns detected for this query.")

                    st.divider()

                    # ── 13. Line-by-Line SQL Explanation ─────────────────────
                    with st.expander("💬 Line-by-Line Explanation", expanded=False):
                        _exp_lines = [ln for ln in analysis["query"].splitlines() if ln.strip()]
                        st.markdown(
                            '<div class="sql-exp-row">'
                            '<div class="sql-exp-hdr">SQL Line</div>'
                            '<div class="sql-exp-hdr" style="padding-left:12px;">Business Meaning</div>'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                        for _ln in _exp_lines:
                            _meaning   = _explain_sql_line(_ln)
                            _code_esc  = html_lib.escape(_ln.strip())
                            st.markdown(
                                f'<div class="sql-exp-row">'
                                f'<div class="sql-exp-code">{_code_esc}</div>'
                                f'<div class="sql-exp-text">{_meaning}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    # ── 14. Original SQL ──────────────────────────────────────
                    with st.expander("🧾 Original SQL", expanded=False):
                        st.code(analysis["query"], language="sql")


        with _ta_java:
            # ── Lazy-load analysis ─────────────────────────────────────────────────
            _jl_cache_key = f"_java_logic_{job_name}"
            if _jl_cache_key not in st.session_state:
                st.session_state[_jl_cache_key] = analyze_java_logic(job)
            _jl = st.session_state[_jl_cache_key]

            # ── Global dashboard CSS ───────────────────────────────────────────────
            st.markdown("""
            <style>
            .jl-header{display:flex;align-items:center;gap:12px;margin-bottom:4px;}
            .jl-header-title{font-size:22px;font-weight:800;color:#1a1a18;letter-spacing:-.02em;}
            .jl-header-sub{font-size:13px;color:#8a8a85;margin-bottom:20px;}
            .jl-kpi-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:20px;}
            .jl-kpi-card{border:1px solid #e4e3dc;border-radius:12px;padding:14px 16px;background:#fff;}
            .jl-kpi-label{font-size:10px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;}
            .jl-kpi-value{font-size:26px;font-weight:800;color:#1a1a18;line-height:1;}
            .jl-kpi-sub{font-size:11px;color:#8a8a85;margin-top:4px;}
            .jl-badge{display:inline-block;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;letter-spacing:.04em;}
            .jl-divider{border:none;border-top:1px solid #e4e3dc;margin:18px 0;}
            .jl-section-label{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;}
            </style>""", unsafe_allow_html=True)

            # ── Page header ────────────────────────────────────────────────────────
            _jl_comps = _jl["components"]
            _jl_risk_color = {"CRITICAL": "#be123c", "HIGH": "#c2500a", "MEDIUM": "#1d4ed8", "LOW": "#166534"}.get(_jl["overall_risk"], "#374151")
            _jl_risk_bg    = {"CRITICAL": "#fff1f2", "HIGH": "#fff7ed", "MEDIUM": "#eff6ff", "LOW": "#f0fdf4"}.get(_jl["overall_risk"], "#f9fafb")
            st.markdown(
                f'<div class="jl-header">'
                f'<span class="jl-header-title">&#9749; Java Logic Analysis</span>'
                f'<span class="jl-badge" style="color:{_jl_risk_color};background:{_jl_risk_bg};">{_jl["overall_risk"]} RISK</span>'
                f'</div>'
                f'<div class="jl-header-sub">Custom Java components detected in <strong>{job_name}</strong></div>',
                unsafe_allow_html=True)

            # ── KPI strip ─────────────────────────────────────────────────────────
            _jl_cx_color = {"CRITICAL": "#be123c", "HIGH": "#c2500a", "MEDIUM": "#1d4ed8", "LOW": "#166534"}.get(
                "CRITICAL" if _jl["max_complexity_score"] >= 70 else
                "HIGH"     if _jl["max_complexity_score"] >= 45 else
                "MEDIUM"   if _jl["max_complexity_score"] >= 20 else "LOW", "#374151")
            _jl_jar_color = "#be123c" if len(_jl["external_jars"]) > 0 else "#166534"
            _jl_jar_bg    = "#fff1f2" if len(_jl["external_jars"]) > 0 else "#f0fdf4"
            st.markdown(
                f'<div class="jl-kpi-grid">'
                f'<div class="jl-kpi-card" style="border-left:4px solid #3C3489;">'
                f'<div class="jl-kpi-label">Java Components</div>'
                f'<div class="jl-kpi-value" style="color:#3C3489;">{_jl["java_component_count"]}</div>'
                f'<div class="jl-kpi-sub">tJava / tJavaRow / tJavaFlex</div></div>'
                f'<div class="jl-kpi-card" style="border-left:4px solid #0f766e;">'
                f'<div class="jl-kpi-label">Total LOC</div>'
                f'<div class="jl-kpi-value" style="color:#0f766e;">{_jl["total_loc"]}</div>'
                f'<div class="jl-kpi-sub">non-blank lines</div></div>'
                f'<div class="jl-kpi-card" style="border-left:4px solid {_jl_cx_color};">'
                f'<div class="jl-kpi-label">Peak Complexity</div>'
                f'<div class="jl-kpi-value" style="color:{_jl_cx_color};">{_jl["max_complexity_score"]}</div>'
                f'<div class="jl-kpi-sub">status</div></div>'
                f'<div class="jl-kpi-card" style="border-left:4px solid {_jl_risk_color};background:{_jl_risk_bg};">'
                f'<div class="jl-kpi-label">Overall Risk</div>'
                f'<div class="jl-kpi-value" style="color:{_jl_risk_color};font-size:18px;">{_jl["overall_risk"]}</div>'
                f'<div class="jl-kpi-sub">migration exposure</div></div>'
                f'<div class="jl-kpi-card" style="border-left:4px solid {_jl_jar_color};background:{_jl_jar_bg};">'
                f'<div class="jl-kpi-label">External JARs</div>'
                f'<div class="jl-kpi-value" style="color:{_jl_jar_color};">{len(_jl["external_jars"])}</div>'
                f'<div class="jl-kpi-sub">{"require bundling" if _jl["external_jars"] else "none detected"}</div></div>'
                f'</div><hr class="jl-divider">',
                unsafe_allow_html=True)

            _jl_overview_tabs = st.tabs(["Java Inventory", "Complexity & Risk", "AI Explanation", "Recommendations"])
            with _jl_overview_tabs[0]:
                st.markdown("#### Java Inventory")
                _inv_rows = _jl.get("java_inventory", [])
                if _inv_rows:
                    st.dataframe(pd.DataFrame(_inv_rows), use_container_width=True, hide_index=True)
                else:
                    st.caption("No tJava / tJavaRow / tJavaFlex inventory rows detected for this job.")

                _inv_c1, _inv_c2 = st.columns(2)
                with _inv_c1:
                    st.markdown("##### Routines")
                    _routines = _jl.get("routine_usage", {})
                    if _routines:
                        st.dataframe(
                            pd.DataFrame(
                                [{"Routine": name, "References": count} for name, count in sorted(_routines.items(), key=lambda x: -x[1])]
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.caption("No custom routine references detected.")
                with _inv_c2:
                    st.markdown("##### External Libraries")
                    _jars = _jl.get("external_jars", [])
                    if _jars:
                        st.dataframe(pd.DataFrame({"External Library": _jars}), use_container_width=True, hide_index=True)
                    else:
                        st.caption("No external Java libraries detected.")

            with _jl_overview_tabs[1]:
                st.markdown("#### Complexity & Risk")
                _risk_rows = []
                for _c in _jl_comps:
                    _risk_rows.append({
                        "Component": _c.get("uid", ""),
                        "Type": _c.get("component_type", ""),
                        "LOC": _c.get("loc", 0),
                        "Complexity": _c.get("complexity", {}).get("label", ""),
                        "Complexity Score": _c.get("complexity", {}).get("score", 0),
                        "Risk": _c.get("risk", {}).get("overall", ""),
                        "Risk Findings": "; ".join(f.get("reason", "") for f in _c.get("risk", {}).get("findings", [])),
                    })
                if _risk_rows:
                    st.dataframe(pd.DataFrame(_risk_rows), use_container_width=True, hide_index=True)
                else:
                    st.caption("No Java complexity or risk records detected.")

            with _jl_overview_tabs[2]:
                st.markdown("#### AI Explanation")
                st.info(_jl.get("ai_explanation", "No Java explanation available."))

            with _jl_overview_tabs[3]:
                st.markdown("#### Recommendations")
                _rec_rows = _jl.get("recommendations", [])
                if _rec_rows:
                    st.dataframe(pd.DataFrame(_rec_rows), use_container_width=True, hide_index=True)
                else:
                    st.success("No Java migration recommendations needed.")

            st.markdown("<hr class='jl-divider'>", unsafe_allow_html=True)

            if not _jl_comps:
                st.info("No tJava / tJavaRow / tJavaFlex components found in this job.")
            else:
                # ── Component selector ─────────────────────────────────────────────
                _RISK_COLOR_SEL = {"CRITICAL": "#be123c", "HIGH": "#c2500a", "MEDIUM": "#1d4ed8", "LOW": "#166534"}
                _RISK_BG_SEL    = {"CRITICAL": "#fff1f2", "HIGH": "#fff7ed", "MEDIUM": "#eff6ff", "LOW": "#f0fdf4"}

                _comp_labels = [f"{c['uid']} ({c['component_type']})" for c in _jl_comps]
                _sel_comp_idx = st.selectbox(
                    "Select Java Component",
                    range(len(_comp_labels)),
                    format_func=lambda i: _comp_labels[i],
                    key=f"java_comp_sel_{job_name}",
                )
                _comp = _jl_comps[_sel_comp_idx]

                # ── Component list cards ───────────────────────────────────────────
                _cl_css = """
                <style>
                .cl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;margin-bottom:14px;}
                .cl-card{border:1px solid #e4e3dc;border-radius:9px;padding:10px 12px;cursor:default;}
                .cl-card-active{border-color:#3C3489;box-shadow:0 0 0 2px #3C348922;}
                .cl-name{font-size:12.5px;font-weight:700;color:#2d2d2a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:4px;}
                .cl-row{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-top:3px;}
                .cl-type{font-size:10px;color:#8a8a85;background:#f3f4f6;border-radius:4px;padding:1px 6px;white-space:nowrap;}
                .cl-loc{font-size:10px;color:#6b7280;}
                .cl-risk{font-size:10px;font-weight:700;border-radius:20px;padding:1px 7px;white-space:nowrap;}
                </style>"""
                st.markdown(_cl_css, unsafe_allow_html=True)

                _cl_cards = ""
                for _ci, _cc in enumerate(_jl_comps):
                    _cc_risk = _cc.get("risk", {}).get("overall", "LOW")
                    _cc_cx   = _cc.get("complexity", {})
                    _cc_loc  = _cc.get("loc", 0)
                    _cc_rc   = _RISK_COLOR_SEL.get(_cc_risk, "#374151")
                    _cc_rb   = _RISK_BG_SEL.get(_cc_risk, "#f9fafb")
                    _active  = "cl-card-active" if _ci == _sel_comp_idx else ""
                    _cl_cards += f"""
                    <div class="cl-card {_active}">
                      <div class="cl-name" title="{_cc['uid']}">{_cc['uid']}</div>
                      <div class="cl-row">
                        <span class="cl-type">{_cc['component_type']}</span>
                        <span class="cl-loc">{_cc_loc} LOC</span>
                        <span class="cl-risk" style="color:{_cc_rc};background:{_cc_rb};">{_cc_risk}</span>
                      </div>
                    </div>"""
                st.markdown(f"<div class='cl-grid'>{_cl_cards}</div>", unsafe_allow_html=True)

                # ── Sub-tabs ───────────────────────────────────────────────────────
                _jt_rules, _jt_pseudo, _jt_biz_rules, _jt_inputs, _jt_outputs, _jt_flow, _jt_risk, _jt_deps, _jt_code = st.tabs(
                    ["Business Function", "Rules & Logic", "Business Rules", "Inputs", "Outputs", "Process Flow", "Migration Impact", "Dependencies", "Technical Code"]
                )
                # Technical Code ───────────────────────────────────────────────────
                with _jt_code:
                    # ── Metric strip ───────────────────────────────────────────────
                    _tc_cx = _comp["complexity"]
                    _TC_RISK_COLOR = {"CRITICAL": "#be123c", "HIGH": "#c2500a", "MEDIUM": "#1d4ed8", "LOW": "#166534"}
                    _TC_RISK_BG    = {"CRITICAL": "#fff1f2", "HIGH": "#fff7ed", "MEDIUM": "#eff6ff", "LOW": "#f0fdf4"}
                    _tc_cx_col = _TC_RISK_COLOR.get(_tc_cx["label"], "#374151")
                    _tc_cx_bg  = _TC_RISK_BG.get(_tc_cx["label"], "#f9fafb")
                    st.markdown(f"""
                    <style>
                    .tc-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px;}}
                    .tc-card{{border:1px solid #e4e3dc;border-radius:10px;padding:11px 14px;}}
                    .tc-label{{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px;}}
                    .tc-value{{font-size:20px;font-weight:800;line-height:1.1;}}
                    .tc-sub{{font-size:11px;color:#8a8a85;margin-top:3px;}}
                    </style>
                    <div class='tc-grid'>
                      <div class='tc-card' style='border-left:4px solid #3C3489;background:#f5f4ff;'>
                        <div class='tc-label'>Component Type</div>
                        <div class='tc-value' style='color:#3C3489;font-size:15px;'>{_comp["component_type"]}</div>
                        <div class='tc-sub'>{_comp["uid"]}</div>
                      </div>
                      <div class='tc-card' style='border-left:4px solid #0f766e;background:#f0fdfa;'>
                        <div class='tc-label'>Lines of Code</div>
                        <div class='tc-value' style='color:#0f766e;'>{_comp["loc"]}</div>
                        <div class='tc-sub'>non-blank lines</div>
                      </div>
                      <div class='tc-card' style='border-left:4px solid {_tc_cx_col};background:{_tc_cx_bg};'>
                        <div class='tc-label'>Complexity</div>
                        <div class='tc-value' style='color:{_tc_cx_col};'>{_tc_cx["label"]}</div>
                        <div class='tc-sub'>Status: {_tc_cx["label"]}</div>
                      </div>
                    </div>""", unsafe_allow_html=True)

                    st.markdown(f"_{_comp['explanation']}_")
                    st.markdown("**Detected patterns:**")
                    _flag_names = {
                        "file_operations": "File I/O",
                        "jdbc_calls": "JDBC / DB",
                        "runtime_exec": "Runtime Exec",
                        "string_manip": "String Manipulation",
                        "loops": "Loops",
                        "conditionals": "Conditionals",
                        "error_handling": "Error Handling",
                        "system_env": "System Env / Properties",
                        "collections": "Collections (List/Map)",
                        "math_ops": "Math Operations",
                        "date_ops": "Date / Time",
                        "external_jar": "External Import",
                    }
                    _flag_cols = st.columns(4)
                    for _fi, (_fk, _fl) in enumerate(_flag_names.items()):
                        with _flag_cols[_fi % 4]:
                            _icon = "✅" if _comp["flags"].get(_fk) else "⬜"
                            st.markdown(f"{_icon} {_fl}")
                    if _comp.get("external_jars"):
                        st.markdown("**External JARs detected:**")
                        for _jar in _comp["external_jars"]:
                            st.markdown(f"- `{_jar}`")
                    if _comp["code"]:
                        st.code(_comp["code"], language="java")
                    else:
                        st.caption("No extractable code found in component parameters.")

                # Business Function ────────────────────────────────────────────────
                with _jt_rules:
                    _flags = _comp["flags"]
                    _risk  = _comp["risk"]
                    _cx    = _comp["complexity"]

                    # ── Purpose ───────────────────────────────────────────────────
                    _purpose = _comp["explanation"]
                    # ── Business Process ──────────────────────────────────────────
                    _process_items = []
                    if _flags.get("file_operations"):  _process_items.append("File read/write operations")
                    if _flags.get("jdbc_calls"):        _process_items.append("Direct database query execution")
                    if _flags.get("runtime_exec"):      _process_items.append("External OS process execution")
                    if _flags.get("string_manip"):      _process_items.append("String transformation and parsing")
                    if _flags.get("date_ops"):          _process_items.append("Date and time processing")
                    if _flags.get("math_ops"):          _process_items.append("Numeric/mathematical computation")
                    if _flags.get("collections"):       _process_items.append("Collection/list management")
                    if not _process_items:              _process_items.append("Custom Java processing")
                    # ── Inputs ────────────────────────────────────────────────────
                    _inputs = []
                    if _flags.get("jdbc_calls"):   _inputs.append("Database records via JDBC")
                    if _flags.get("file_operations"): _inputs.append("Local file system data")
                    if _flags.get("system_env"):   _inputs.append("System environment / JVM properties")
                    if _jl["routine_usage"]:       _inputs.append(f"Custom routines: {', '.join(list(_jl['routine_usage'].keys())[:3])}")
                    if not _inputs:                _inputs.append("Row data from upstream Talend components")
                    # ── Outputs ───────────────────────────────────────────────────
                    _outputs = []
                    if _flags.get("jdbc_calls"):      _outputs.append("Database write / query result")
                    if _flags.get("file_operations"): _outputs.append("Written file output")
                    if _flags.get("runtime_exec"):    _outputs.append("OS process result / exit code")
                    if not _outputs:                  _outputs.append("Transformed row data to downstream components")
                    # ── Key Decisions ─────────────────────────────────────────────
                    _decisions = _comp["business_rules"]
                    # ── Business Impact ───────────────────────────────────────────
                    _impact_color = {"CRITICAL": "#be123c", "HIGH": "#c2500a", "MEDIUM": "#1d4ed8", "LOW": "#166534"}.get(_risk["overall"], "#374151")
                    _impact_icon  = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(_risk["overall"], "⚪")
                    _impact_lines = [f"Migration risk: **{_risk['overall']}** — {_risk['findings'][0]['reason']}"]
                    _impact_lines.append(f"Complexity Status: **{_cx['label']}")
                    if _comp["external_jars"]:
                        _impact_lines.append(f"External JARs require bundling: {', '.join(_comp['external_jars'][:3])}")

                    st.markdown(f"#### Business Function — {_comp['uid']}")
                    st.caption(f"`{_comp['component_type']}` · {_comp['loc']} lines of custom Java")

                    # ── Top summary card ───────────────────────────────────────────
                    _bf_outcome = (
                        f"Produces {', '.join(_outputs[:2])}" if _outputs else "Delivers transformed data to downstream components"
                    )
                    _bf_why_parts = []
                    if _flags.get("jdbc_calls"):      _bf_why_parts.append("direct database access is required")
                    if _flags.get("file_operations"): _bf_why_parts.append("file system interaction is needed")
                    if _flags.get("runtime_exec"):    _bf_why_parts.append("an external system process must be invoked")
                    if _flags.get("string_manip"):    _bf_why_parts.append("custom text formatting cannot be handled by standard components")
                    if _flags.get("math_ops"):        _bf_why_parts.append("numeric calculations are required")
                    if _flags.get("date_ops"):        _bf_why_parts.append("date parsing or formatting logic is needed")
                    if not _bf_why_parts:             _bf_why_parts.append("the logic cannot be expressed using standard Talend components alone")
                    _bf_why = "Used because " + " and ".join(_bf_why_parts[:2]) + "."

                    _bf_summary_css = """
                    <style>
                    .bfs-card{border:2px solid #3C3489;border-radius:12px;padding:16px 18px;margin-bottom:14px;background:linear-gradient(135deg,#f5f4ff 0%,#fff 100%);}
                    .bfs-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;border-top:1px solid #e4e3dc;margin-top:12px;padding-top:12px;}
                    .bfs-col{padding:0 14px;}
                    .bfs-col:first-child{padding-left:0;}
                    .bfs-col:not(:last-child){border-right:1px solid #e4e3dc;}
                    .bfs-col-label{font-size:10px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px;}
                    .bfs-col-text{font-size:12.5px;color:#2d2d2a;line-height:1.55;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
                    .bfs-title{font-size:13px;font-weight:700;color:#3C3489;margin-bottom:4px;}
                    .bfs-purpose{font-size:13px;color:#2d2d2a;line-height:1.6;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
                    </style>"""
                    st.markdown(_bf_summary_css, unsafe_allow_html=True)
                    st.markdown(f"""<div class="bfs-card">
                      <div class="bfs-title">📋 {_comp['uid']}</div>
                      <div class="bfs-purpose">{_purpose}</div>
                      <div class="bfs-row">
                        <div class="bfs-col">
                          <div class="bfs-col-label">🎯 Business Outcome</div>
                          <div class="bfs-col-text">{_bf_outcome}</div>
                        </div>
                        <div class="bfs-col">
                          <div class="bfs-col-label">❓ Why Used</div>
                          <div class="bfs-col-text">{_bf_why}</div>
                        </div>
                        <div class="bfs-col">
                          <div class="bfs-col-label">⚠️ Migration Risk</div>
                          <div class="bfs-col-text">{_impact_icon} <strong>{_risk['overall']}</strong> — {_risk['findings'][0]['reason']}</div>
                        </div>
                      </div>
                    </div>""", unsafe_allow_html=True)

                    _bf_css = """
                    <style>
                    .bf-card{background:#fff;border:1px solid #e4e3dc;border-radius:12px;padding:14px 16px;margin-bottom:10px;}
                    .bf-card-title{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px;}
                    .bf-card-body{font-size:13px;color:#2d2d2a;line-height:1.65;}
                    .bf-card-body ul{margin:0;padding-left:18px;}
                    .bf-card-body li{margin-bottom:3px;}
                    .bf-impact{border-left:4px solid """ + _impact_color + """;}
                    </style>"""
                    st.markdown(_bf_css, unsafe_allow_html=True)

                    # Row 1: Purpose (full width)
                    st.markdown(f"""<div class="bf-card">
                      <div class="bf-card-title">📌 Purpose</div>
                      <div class="bf-card-body">{_purpose}</div>
                    </div>""", unsafe_allow_html=True)

                    # Row 2: Business Process | Key Decisions
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        _proc_html = "".join(f"<li>{i}</li>" for i in _process_items)
                        st.markdown(f"""<div class="bf-card">
                          <div class="bf-card-title">⚙️ Business Process</div>
                          <div class="bf-card-body"><ul>{_proc_html}</ul></div>
                        </div>""", unsafe_allow_html=True)
                    with _c2:
                        _dec_html = "".join(f"<li>{d}</li>" for d in _decisions)
                        st.markdown(f"""<div class="bf-card">
                          <div class="bf-card-title">🔀 Key Decisions</div>
                          <div class="bf-card-body"><ul>{_dec_html}</ul></div>
                        </div>""", unsafe_allow_html=True)

                    # Row 3: Inputs | Outputs
                    _c3, _c4 = st.columns(2)
                    with _c3:
                        _in_html = "".join(f"<li>{i}</li>" for i in _inputs)
                        st.markdown(f"""<div class="bf-card">
                          <div class="bf-card-title">📥 Inputs</div>
                          <div class="bf-card-body"><ul>{_in_html}</ul></div>
                        </div>""", unsafe_allow_html=True)
                    with _c4:
                        _out_html = "".join(f"<li>{o}</li>" for o in _outputs)
                        st.markdown(f"""<div class="bf-card">
                          <div class="bf-card-title">📤 Outputs</div>
                          <div class="bf-card-body"><ul>{_out_html}</ul></div>
                        </div>""", unsafe_allow_html=True)

                    # Row 4: Business Impact (full width)
                    _imp_html = "".join(f"<li>{l}</li>" for l in _impact_lines)
                    st.markdown(f"""<div class="bf-card bf-impact">
                      <div class="bf-card-title">{_impact_icon} Business Impact</div>
                      <div class="bf-card-body"><ul>{_imp_html}</ul></div>
                    </div>""", unsafe_allow_html=True)

                    # ── AI Business Function Summary ──────────────────────────────────────────
                    st.markdown("---")
                    _bf_ai_key = f"bf_ai_summary_{job_name}_{_comp['uid']}"
                    _bf_use_ai = st.checkbox("\U0001f916 Use AI (Ollama)", value=False, key=f"bf_use_ai_{job_name}_{_comp['uid']}")
                    if st.button("\u2728 Generate Business Function Summary", key=f"btn_bf_ai_{job_name}_{_comp['uid']}"):
                        _bf_prompt = (
                            "You are a business analyst writing a plain-English summary of a data integration component.\n"
                            "Audience: Business Analysts, Architects, Junior Developers.\n"
                            "Rules:\n"
                            "- Use business language only. No Java, no code, no variable names, no method names.\n"
                            "- Describe WHAT this component does for the business, not HOW it works technically.\n"
                            "- Write in clear paragraphs. No bullet points. No lists.\n"
                            "- Keep it under 150 words.\n\n"
                            f"Component name: {_comp['uid']}\n"
                            f"Component type: {_comp['component_type']}\n"
                            f"What it does: {_purpose}\n"
                            f"Business activities: {', '.join(_process_items)}\n"
                            f"What it receives: {', '.join(_inputs)}\n"
                            f"What it produces: {', '.join(_outputs)}\n"
                            f"Business decisions made: {', '.join(_decisions)}\n"
                            f"Migration risk: {_risk['overall']}\n"
                            f"Complexity level: {_cx['label']}\n\n"
                            "Write a plain-English business summary of what this component does and why it matters."
                        )
                        with st.spinner("Generating business summary\u2026"):
                            st.session_state[_bf_ai_key] = ask_ollama(_bf_prompt, use_ollama=_bf_use_ai)

                    _bf_summary = st.session_state.get(_bf_ai_key)
                    if _bf_summary:
                        st.markdown(
                            '<div class="bf-card" style="border-left:4px solid #3C3489;">' +
                            '<div class="bf-card-title">\U0001f9e0 AI Business Summary</div>' +
                            f'<div class="bf-card-body" style="white-space:pre-wrap;">{_bf_summary}</div></div>',
                            unsafe_allow_html=True
                        )

                # Rules & Logic ────────────────────────────────────────────────────
                with _jt_pseudo:
                    st.markdown(f"#### Rules & Logic — {_comp['uid']}")
                    st.caption("Business rules extracted from this component. No code — business language only.")

                    # ── Build business rules table ─────────────────────────────────
                    _rl_flags = _comp["flags"]
                    _rl_raw_rules = _comp["business_rules"]

                    _RULE_MAP = [
                        ("conditionals",   "Conditional Branching",     "When a data condition is evaluated as true or false",         "Route or transform records differently depending on field values",                "Ensures only matching records follow the correct processing path"),
                        ("loops",          "Iterative Processing",      "When a batch or collection of records is available",          "Process each record or item one at a time in sequence",                           "Handles multiple rows or items without manual repetition"),
                        ("jdbc_calls",     "Direct Database Access",    "When the component needs to read or write database data",     "Execute a database query and process the returned records",                       "Retrieves or persists data outside of standard Talend connectors"),
                        ("file_operations","File Read / Write",         "When a file path is available on the local system",          "Open, read, or write data to a file on disk",                                     "Moves data to or from the file system as part of the pipeline"),
                        ("string_manip",   "Text Transformation",       "When a text field requires cleaning or reformatting",        "Split, replace, trim, or reformat string values",                                 "Ensures data conforms to downstream format requirements"),
                        ("date_ops",       "Date & Time Handling",      "When a date or timestamp field is present",                  "Parse, format, or calculate date and time values",                                "Converts dates into the required format for downstream systems"),
                        ("math_ops",       "Numeric Calculation",       "When a numeric field requires computation",                  "Perform arithmetic or aggregate calculations on numeric data",                    "Derives calculated values such as totals, averages, or scores"),
                        ("error_handling", "Error & Exception Handling","When an unexpected error occurs during processing",           "Catch the error, log it, and either continue or stop the job",                   "Prevents silent failures and ensures errors are visible and traceable"),
                        ("runtime_exec",   "External Process Execution","When an OS-level command or external program must be called", "Execute an external script or system process and capture its output",            "Integrates with non-Java tools or OS utilities as part of the pipeline"),
                        ("system_env",     "Environment Configuration", "When a runtime setting or environment variable is needed",   "Read a system property or environment variable to configure behaviour",          "Allows the job to adapt to different environments without code changes"),
                        ("collections",    "Collection Management",     "When multiple values must be grouped or looked up",          "Store, retrieve, or iterate over lists, maps, or sets of values",                "Enables in-memory grouping, deduplication, or lookup operations"),
                        ("external_jar",   "External Library Usage",    "When a third-party library function is required",            "Call a function from an external JAR or library bundled with the job",           "Extends job capability using pre-built components not native to Talend"),
                    ]

                    _rl_rows = []
                    for _flag_key, _rule, _condition, _action, _meaning in _RULE_MAP:
                        if _rl_flags.get(_flag_key):
                            _rl_rows.append({
                                "Rule": _rule,
                                "Condition": _condition,
                                "Action": _action,
                                "Meaning": _meaning,
                            })

                    # Add any conditional-level detail from business_rules
                    _cond_details = [r for r in _rl_raw_rules if r.startswith("Conditional logic:")]
                    if _cond_details and _rl_rows:
                        _first_cond = next((i for i, r in enumerate(_rl_rows) if r["Rule"] == "Conditional Branching"), None)
                        if _first_cond is not None:
                            _detail_text = "; ".join(
                                d.replace("Conditional logic: ", "").strip() for d in _cond_details[:3]
                            )
                            _rl_rows[_first_cond]["Condition"] = f"When: {_detail_text}"

                    if not _rl_rows:
                        st.info("No specific business rules were detected in this component. It may perform simple pass-through logic.")
                    else:
                        _rl_css = """
                        <style>
                        .rl-table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px;}
                        .rl-table th{background:#3C3489;color:#fff;padding:8px 12px;text-align:left;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.06em;}
                        .rl-table td{padding:8px 12px;border-bottom:1px solid #e4e3dc;vertical-align:top;color:#2d2d2a;line-height:1.5;}
                        .rl-table tr:last-child td{border-bottom:none;}
                        .rl-table tr:hover td{background:#f5f4f0;}
                        .rl-rule{font-weight:600;color:#3C3489;white-space:nowrap;}
                        </style>"""
                        st.markdown(_rl_css, unsafe_allow_html=True)

                        _thead = "<tr><th>Rule</th><th>Condition</th><th>Action</th><th>Meaning</th></tr>"
                        _tbody = "".join(
                            f"<tr><td class='rl-rule'>{r['Rule']}</td><td>{r['Condition']}</td><td>{r['Action']}</td><td>{r['Meaning']}</td></tr>"
                            for r in _rl_rows
                        )
                        st.markdown(
                            f"<table class='rl-table'><thead>{_thead}</thead><tbody>{_tbody}</tbody></table>",
                            unsafe_allow_html=True,
                        )

                        st.markdown("")
                        st.caption(f"**Summary:** {_comp['explanation']}")

                # Business Rules ───────────────────────────────────────────────────
                with _jt_biz_rules:
                    import json as _json_br
                    st.markdown(f"#### Business Rules — {_comp['uid']}")
                    st.caption("Plain-English business rules derived from this component's Java logic, enriched with the Business Dictionary.")

                    # ── Load java_dictionary ───────────────────────────────────────
                    _br_dict_path = "config/java_dictionary.json"
                    try:
                        with open(_br_dict_path, "r") as _br_f:
                            _br_dict = _json_br.load(_br_f)
                    except Exception:
                        logger.exception("Failed to load Java business dictionary; using empty dictionary.")
                        _br_dict = {"keywords": {}, "types": {}, "patterns": {}}

                    _br_kw   = _br_dict.get("keywords", {})
                    _br_ty   = _br_dict.get("types", {})
                    _br_pat  = _br_dict.get("patterns", {})
                    _br_code = _comp.get("code", "")
                    _br_flags = _comp["flags"]
                    _br_raw_rules = _comp["business_rules"]

                    # ── CSS ────────────────────────────────────────────────────────
                    st.markdown("""
                    <style>
                    .br-section{margin-bottom:18px;}
                    .br-section-label{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;}
                    .br-card{background:#fff;border:1px solid #e4e3dc;border-radius:10px;padding:12px 15px;margin-bottom:8px;}
                    .br-card-row{display:flex;align-items:flex-start;gap:12px;}
                    .br-icon{font-size:18px;flex-shrink:0;margin-top:1px;}
                    .br-term{font-size:13px;font-weight:700;color:#3C3489;margin-bottom:2px;}
                    .br-expl{font-size:12.5px;color:#4b5563;line-height:1.55;}
                    .br-badge{display:inline-block;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;background:#f5f4ff;color:#3C3489;border:1px solid #c7c4f0;margin-bottom:4px;}
                    .br-cond-card{border-left:4px solid #3C3489;background:#f5f4ff;border-radius:8px;padding:10px 13px;margin-bottom:6px;font-size:12.5px;color:#2d2d2a;line-height:1.55;}
                    .br-cond-label{font-size:10px;font-weight:700;color:#3C3489;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px;}
                    .br-type-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;margin-top:4px;}
                    .br-type-card{border:1px solid #e4e3dc;border-radius:8px;padding:9px 12px;background:#fff;}
                    .br-type-name{font-size:11px;font-weight:700;color:#8a8a85;margin-bottom:2px;}
                    .br-type-term{font-size:13px;font-weight:700;color:#0f766e;}
                    .br-type-expl{font-size:11.5px;color:#6b7280;line-height:1.45;margin-top:2px;}
                    .br-pat-card{border-left:4px solid #0f766e;background:#f0fdfa;border-radius:8px;padding:9px 13px;margin-bottom:6px;}
                    .br-pat-term{font-size:12.5px;font-weight:700;color:#0f766e;margin-bottom:2px;}
                    .br-pat-expl{font-size:12px;color:#374151;line-height:1.5;}
                    .br-empty{font-size:13px;color:#9ca3af;font-style:italic;padding:12px 0;}
                    </style>""", unsafe_allow_html=True)

                    # ── Section 1: Keyword-level Business Rules ────────────────────
                    st.markdown("<div class='br-section-label'>🔑 Keyword Business Rules (from Business Dictionary)</div>", unsafe_allow_html=True)
                    _br_kw_icons = {
                        "if": "🔀", "else": "↩️", "for": "🔁", "while": "🔄",
                        "try": "⚙️", "catch": "🚨", "return": "📤", "throw": "⚠️",
                        "switch": "🗂️", "break": "⏹️", "continue": "⏭️", "import": "📦",
                    }
                    _br_found_kw = []
                    for _kw, _kw_info in _br_kw.items():
                        # Check if keyword appears in the component code
                        _pat = rf"\b{_kw}\b" if _kw not in ("import",) else rf"\b{_kw}\s+"
                        if re.search(_pat, _br_code):
                            _br_found_kw.append((_kw, _kw_info))

                    if _br_found_kw:
                        _br_kw_html = ""
                        for _kw, _kw_info in _br_found_kw:
                            _ico = _br_kw_icons.get(_kw, "📋")
                            _br_kw_html += f"""<div class="br-card">
                              <div class="br-card-row">
                                <div class="br-icon">{_ico}</div>
                                <div>
                                  <div class="br-badge">{_kw}</div>
                                  <div class="br-term">{_kw_info['business_term']}</div>
                                  <div class="br-expl">{_kw_info['explanation']}</div>
                                </div>
                              </div>
                            </div>"""
                        st.markdown(_br_kw_html, unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='br-empty'>No keyword-level business rules detected in this component.</div>", unsafe_allow_html=True)

                    st.markdown("<hr style='border:none;border-top:1px solid #e4e3dc;margin:14px 0;'>", unsafe_allow_html=True)

                    # ── Section 2: Extracted Conditional Rules ─────────────────────
                    st.markdown("<div class='br-section-label'>🔍 Extracted Conditional Business Rules</div>", unsafe_allow_html=True)
                    _br_cond_matches = re.findall(r"if\s*\((.{0,120})\)", _br_code)
                    if _br_cond_matches:
                        _br_cond_html = ""
                        for _ci, _cond in enumerate(_br_cond_matches[:8]):
                            _cond_clean = _cond.strip()
                            # Enrich: detect null checks, string compares, numeric compares
                            if "null" in _cond_clean.lower():
                                _cond_biz = f"Check: Is the value present? (Missing Value Check)"
                            elif any(op in _cond_clean for op in ("==", "!=", ".equals")):
                                _cond_biz = f"Check: Does the value match the required criteria? (Text / Value Match Rule)"
                            elif any(op in _cond_clean for op in (">", "<", ">=", "<=")):
                                _cond_biz = f"Check: Does the value fall within the required range? (Threshold / Range Rule)"
                            elif "isEmpty" in _cond_clean or "length" in _cond_clean:
                                _cond_biz = f"Check: Is the field populated? (Presence Validation Rule)"
                            else:
                                _cond_biz = f"Business condition evaluated to determine the processing path."
                            _br_cond_html += f"""<div class="br-cond-card">
                              <div class="br-cond-label">Rule {_ci + 1}</div>
                              <div><strong>Condition:</strong> <code>{_cond_clean[:100]}</code></div>
                              <div style="margin-top:4px;color:#6b7280;">{_cond_biz}</div>
                            </div>"""
                        st.markdown(_br_cond_html, unsafe_allow_html=True)
                        if len(_br_cond_matches) > 8:
                            st.caption(f"Showing 8 of {len(_br_cond_matches)} conditions detected.")
                    else:
                        st.markdown("<div class='br-empty'>No conditional (if) statements detected in this component.</div>", unsafe_allow_html=True)

                    st.markdown("<hr style='border:none;border-top:1px solid #e4e3dc;margin:14px 0;'>", unsafe_allow_html=True)

                    # ── Section 3: Data Type Business Translations ─────────────────
                    st.markdown("<div class='br-section-label'>🏷️ Data Types in Business Language</div>", unsafe_allow_html=True)
                    _br_found_types = []
                    for _ty, _ty_info in _br_ty.items():
                        _ty_pat = rf"\b{re.escape(_ty)}\b"
                        if re.search(_ty_pat, _br_code):
                            _br_found_types.append((_ty, _ty_info))

                    if _br_found_types:
                        _br_type_html = "<div class='br-type-grid'>"
                        for _ty, _ty_info in _br_found_types:
                            _br_type_html += f"""<div class="br-type-card">
                              <div class="br-type-name">{_ty}</div>
                              <div class="br-type-term">{_ty_info['business_term']}</div>
                              <div class="br-type-expl">{_ty_info['explanation']}</div>
                            </div>"""
                        _br_type_html += "</div>"
                        st.markdown(_br_type_html, unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='br-empty'>No recognised data types detected in this component.</div>", unsafe_allow_html=True)

                    st.markdown("<hr style='border:none;border-top:1px solid #e4e3dc;margin:14px 0;'>", unsafe_allow_html=True)

                    # ── Section 4: Pattern-level Business Rules ────────────────────
                    st.markdown("<div class='br-section-label'>🔬 Code Pattern Rules</div>", unsafe_allow_html=True)
                    _br_pattern_checks = {
                        "null_check":       r"\bnull\b",
                        "string_compare":   r"\.equals\s*\(|==\s*\"",
                        "numeric_compare":  r"\b(>|<|>=|<=)\s*\d",
                        "date_compare":     r"\b(before|after|compareTo)\s*\(",
                        "regex_match":      r"\.matches\s*\(|Pattern\.|matches\(",
                        "trim_normalize":   r"\.trim\s*\(\)|\.toLowerCase\s*\(\)|\.toUpperCase\s*\(\)",
                    }
                    _br_found_pats = []
                    for _pk, _pp in _br_pattern_checks.items():
                        if re.search(_pp, _br_code) and _pk in _br_pat:
                            _br_found_pats.append((_pk, _br_pat[_pk]))

                    if _br_found_pats:
                        _br_pat_html = ""
                        for _pk, _pi in _br_found_pats:
                            _br_pat_html += f"""<div class="br-pat-card">
                              <div class="br-pat-term">✅ {_pi['business_term']}</div>
                              <div class="br-pat-expl">{_pi['explanation']}</div>
                            </div>"""
                        st.markdown(_br_pat_html, unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='br-empty'>No specific code patterns matched in this component.</div>", unsafe_allow_html=True)

                    st.markdown("<hr style='border:none;border-top:1px solid #e4e3dc;margin:14px 0;'>", unsafe_allow_html=True)

                    # ── Section 5: Raw Extracted Rules (from analyzer) ─────────────
                    st.markdown("<div class='br-section-label'>📋 Analyser-Extracted Rules</div>", unsafe_allow_html=True)
                    _non_cond_rules = [r for r in _br_raw_rules if not r.startswith("Conditional logic:")]
                    _cond_rules     = [r for r in _br_raw_rules if r.startswith("Conditional logic:")]
                    if _non_cond_rules:
                        for _rule_txt in _non_cond_rules:
                            st.markdown(f"- {_rule_txt}")
                    if _cond_rules:
                        with st.expander(f"Conditional detail ({len(_cond_rules)} conditions)", expanded=False):
                            for _cr in _cond_rules:
                                st.markdown(f"- `{_cr.replace('Conditional logic: ', '').strip()}`")
                    if not _non_cond_rules and not _cond_rules:
                        st.markdown("<div class='br-empty'>No rules extracted by the analyser for this component.</div>", unsafe_allow_html=True)

                # Inputs ───────────────────────────────────────────────────────────
                with _jt_inputs:
                    st.markdown(f"#### Inputs — {_comp['uid']}")
                    st.caption("All data sources feeding into this Java component: upstream connections, parameters, context variables, and code-detected sources.")

                    # ── CSS ────────────────────────────────────────────────────────
                    st.markdown("""
                    <style>
                    .inp-section-label{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;margin-top:2px;}
                    .inp-divider{border:none;border-top:1px solid #e4e3dc;margin:14px 0;}
                    .inp-conn-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:8px;margin-bottom:4px;}
                    .inp-conn-card{border:1px solid #e4e3dc;border-radius:10px;padding:11px 14px;background:#fff;}
                    .inp-conn-card-active{border-color:#3C3489;background:#f5f4ff;}
                    .inp-conn-type{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#8a8a85;margin-bottom:3px;}
                    .inp-conn-name{font-size:13.5px;font-weight:700;color:#2d2d2a;margin-bottom:2px;}
                    .inp-conn-ctype{font-size:11px;color:#6b7280;background:#f3f4f6;border-radius:4px;padding:1px 7px;display:inline-block;margin-bottom:3px;}
                    .inp-conn-label{font-size:11px;color:#3C3489;font-weight:600;}
                    .inp-conn-none{font-size:13px;color:#9ca3af;font-style:italic;padding:4px 0;}
                    .inp-param-table{width:100%;border-collapse:collapse;font-size:12.5px;}
                    .inp-param-table th{background:#3C3489;color:#fff;padding:7px 11px;text-align:left;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em;}
                    .inp-param-table td{padding:7px 11px;border-bottom:1px solid #e4e3dc;color:#2d2d2a;vertical-align:top;}
                    .inp-param-table tr:last-child td{border-bottom:none;}
                    .inp-param-table tr:hover td{background:#f5f4f0;}
                    .inp-param-key{font-weight:600;color:#3C3489;white-space:nowrap;}
                    .inp-col-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px;margin-top:4px;}
                    .inp-col-card{border:1px solid #e4e3dc;border-radius:7px;padding:7px 10px;background:#fff;}
                    .inp-col-name{font-size:12px;font-weight:700;color:#2d2d2a;}
                    .inp-col-type{font-size:11px;color:#0f766e;margin-top:1px;}
                    .inp-code-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:8px;font-size:12.5px;margin-bottom:6px;border:1px solid #e4e3dc;}
                    .inp-summary-strip{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;}
                    .inp-kpi{border:1px solid #e4e3dc;border-radius:9px;padding:9px 14px;background:#fff;min-width:110px;}
                    .inp-kpi-label{font-size:10px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px;}
                    .inp-kpi-value{font-size:22px;font-weight:800;color:#3C3489;line-height:1;}
                    .inp-kpi-sub{font-size:11px;color:#8a8a85;margin-top:2px;}
                    </style>""", unsafe_allow_html=True)

                    # ── Gather data ────────────────────────────────────────────────
                    _inp_jd       = job.get("job_data", {})
                    _inp_uid      = _comp["uid"]
                    _inp_all_comp = {c.get("unique_name"): c for c in _inp_jd.get("components", []) if isinstance(c, dict)}
                    _inp_conns    = _inp_jd.get("connections", [])

                    # Upstream FLOW connections into this component
                    _inp_flow_sources = [
                        conn for conn in _inp_conns
                        if conn.get("target") == _inp_uid and conn.get("connector") in ("FLOW", "ITERATE", "LOOKUP", "REJECT", "MAIN")
                    ]
                    # Any connection (including non-FLOW trigger lines)
                    _inp_all_sources = [
                        conn for conn in _inp_conns
                        if conn.get("target") == _inp_uid
                    ]

                    # Component parameters hinting at explicit input sources
                    _inp_params_raw = _comp.get("parameters") or {}
                    _INP_PARAM_KEYS = {
                        "FILE_NAME": ("File Path", "📄"),
                        "FILENAME": ("File Path", "📄"),
                        "TABLE": ("Database Table", "🗄️"),
                        "TABLE_NAME": ("Database Table", "🗄️"),
                        "DBTABLE": ("Database Table", "🗄️"),
                        "QUERY": ("SQL Query", "🔍"),
                        "MEMO_SQL": ("SQL Query", "🔍"),
                        "HOST": ("Database Host", "🌐"),
                        "DBNAME": ("Database Name", "🗄️"),
                        "IMPORT": ("Java Imports", "📦"),
                        "PRECODE": ("Pre-execution Code", "⚙️"),
                    }
                    _inp_explicit_params = [
                        (label, icon, _inp_params_raw[k].strip('"').strip("'"))
                        for k, (label, icon) in _INP_PARAM_KEYS.items()
                        if _inp_params_raw.get(k, "").strip().strip('"').strip("'")
                    ]

                    # Context variable references in code
                    _inp_ctx_refs = sorted(set(re.findall(r'\bcontext\.(\w+)', _comp.get("code", ""))))

                    # Routine usages for this component
                    _inp_routine_refs = {}
                    for v in _inp_params_raw.values():
                        for rname in re.findall(r'\b([A-Z][A-Za-z0-9_]+)\.', str(v)):
                            _inp_routine_refs[rname] = _inp_routine_refs.get(rname, 0) + 1

                    # Code-detected implicit sources from flags
                    _inp_flags = _comp["flags"]
                    _inp_code_sources = []
                    if _inp_flags.get("jdbc_calls"):
                        _inp_code_sources.append(("🗄️", "Database (JDBC)", "Direct database access via JDBC — reads records from a database table or query result.", "#eff6ff", "#1d4ed8"))
                    if _inp_flags.get("file_operations"):
                        _inp_code_sources.append(("📄", "File System", "Reads data from a local file path using Java I/O classes.", "#fffbeb", "#b45309"))
                    if _inp_flags.get("runtime_exec"):
                        _inp_code_sources.append(("⚙️", "External Process", "Reads output from an OS-level process or shell command via Runtime/ProcessBuilder.", "#f5f3ff", "#7c3aed"))
                    if _inp_flags.get("system_env"):
                        _inp_code_sources.append(("🌐", "System / Environment", "Reads configuration values from JVM system properties or OS environment variables.", "#f0fdfa", "#0f766e"))
                    if _inp_flags.get("external_jar"):
                        _inp_code_sources.append(("📦", "External Library", "Receives or processes data via an external JAR library bundled with the job.", "#f0fdf4", "#166534"))

                    # ── KPI strip ──────────────────────────────────────────────────
                    _inp_kpi_html = "<div class='inp-summary-strip'>"
                    _inp_kpi_html += f"""<div class='inp-kpi' style='border-left:4px solid #3C3489;'>
                      <div class='inp-kpi-label'>Upstream Connections</div>
                      <div class='inp-kpi-value'>{len(_inp_flow_sources)}</div>
                      <div class='inp-kpi-sub'>FLOW links into this component</div>
                    </div>"""
                    _inp_kpi_html += f"""<div class='inp-kpi' style='border-left:4px solid #0f766e;'>
                      <div class='inp-kpi-label'>Explicit Parameters</div>
                      <div class='inp-kpi-value'>{len(_inp_explicit_params)}</div>
                      <div class='inp-kpi-sub'>file / table / query inputs</div>
                    </div>"""
                    _inp_kpi_html += f"""<div class='inp-kpi' style='border-left:4px solid #b45309;'>
                      <div class='inp-kpi-label'>Context Variables</div>
                      <div class='inp-kpi-value'>{len(_inp_ctx_refs)}</div>
                      <div class='inp-kpi-sub'>context.* references in code</div>
                    </div>"""
                    _inp_kpi_html += f"""<div class='inp-kpi' style='border-left:4px solid #7c3aed;'>
                      <div class='inp-kpi-label'>Code-Detected Sources</div>
                      <div class='inp-kpi-value'>{len(_inp_code_sources)}</div>
                      <div class='inp-kpi-sub'>implicit input patterns</div>
                    </div>"""
                    _inp_kpi_html += "</div>"
                    st.markdown(_inp_kpi_html, unsafe_allow_html=True)

                    # ── Section 1: Upstream Component Connections ──────────────────
                    st.markdown("<div class='inp-section-label'>🔗 Upstream Component Connections</div>", unsafe_allow_html=True)
                    if _inp_flow_sources:
                        _inp_conn_html = "<div class='inp-conn-grid'>"
                        for _iconn in _inp_flow_sources:
                            _isrc_uid  = _iconn.get("source", "")
                            _isrc_comp = _inp_all_comp.get(_isrc_uid, {})
                            _isrc_ctype = _isrc_comp.get("component_type", "Unknown")
                            _iconn_type = _iconn.get("connector", "FLOW")
                            _iconn_label = (
                                "Data row stream"    if _iconn_type == "FLOW"    else
                                "Iterate trigger"    if _iconn_type == "ITERATE" else
                                "Lookup link"        if _iconn_type == "LOOKUP"  else
                                "Rejected records"   if _iconn_type == "REJECT"  else
                                _iconn_type
                            )
                            # Detect schema columns on the upstream component metadata
                            _isrc_params = _isrc_comp.get("parameters", {})
                            _schema_hint = ""
                            for _sk in ("TABLE", "TABLE_NAME", "DBTABLE", "FILE_NAME", "FILENAME", "QUERY"):
                                _sv = _isrc_params.get(_sk, "").strip('"').strip("'")
                                if _sv:
                                    _schema_hint = f"Source: {_sv[:40]}"
                                    break
                            _inp_conn_html += f"""<div class='inp-conn-card inp-conn-card-active'>
                              <div class='inp-conn-type'>{_iconn_type}</div>
                              <div class='inp-conn-name'>{_isrc_uid}</div>
                              <div><span class='inp-conn-ctype'>{_isrc_ctype}</span></div>
                              <div class='inp-conn-label'>↳ {_iconn_label}</div>
                              {"<div style='font-size:11px;color:#6b7280;margin-top:3px;'>"+_schema_hint+"</div>" if _schema_hint else ""}
                            </div>"""
                        _inp_conn_html += "</div>"
                        st.markdown(_inp_conn_html, unsafe_allow_html=True)

                        # Upstream schema columns (from components with metadata in parsed data)
                        _inp_upstream_cols = []
                        for _iconn in _inp_flow_sources:
                            _isrc_uid = _iconn.get("source", "")
                            _isrc_comp = _inp_all_comp.get(_isrc_uid, {})
                            for _cparam_k, _cparam_v in (_isrc_comp.get("parameters") or {}).items():
                                if "SCHEMA" in _cparam_k.upper() and isinstance(_cparam_v, list):
                                    for _col in _cparam_v:
                                        if isinstance(_col, dict) and _col.get("name"):
                                            _inp_upstream_cols.append({
                                                "name": _col["name"],
                                                "type": _col.get("type", "Unknown"),
                                                "from": _isrc_uid,
                                            })

                        if _inp_upstream_cols:
                            st.markdown("**Upstream Schema Columns**")
                            _inp_col_html = "<div class='inp-col-grid'>"
                            for _icol in _inp_upstream_cols[:24]:
                                _inp_col_html += f"""<div class='inp-col-card'>
                                  <div class='inp-col-name'>{_icol['name']}</div>
                                  <div class='inp-col-type'>{_icol['type']}</div>
                                  <div style='font-size:10px;color:#9ca3af;'>from {_icol['from']}</div>
                                </div>"""
                            if len(_inp_upstream_cols) > 24:
                                _inp_col_html += f"<div class='inp-col-card' style='border-style:dashed;color:#9ca3af;font-size:12px;display:flex;align-items:center;justify-content:center;'>+{len(_inp_upstream_cols)-24} more</div>"
                            _inp_col_html += "</div>"
                            st.markdown(_inp_col_html, unsafe_allow_html=True)
                    else:
                        # Check for any trigger-only connections (OnSubjobOk etc.)
                        _inp_trigger_only = [c for c in _inp_all_sources if c.get("connector") not in ("FLOW", "ITERATE", "LOOKUP", "REJECT", "MAIN")]
                        if _inp_trigger_only:
                            st.markdown(
                                "<div class='inp-conn-none'>No data-flow connections detected. "
                                "This component is triggered by subjob sequencing only — it does not receive row data from an upstream component. "
                                "All input data comes from parameters or code-level sources below.</div>",
                                unsafe_allow_html=True)
                        else:
                            st.markdown("<div class='inp-conn-none'>No upstream connections detected for this component.</div>", unsafe_allow_html=True)

                    st.markdown("<hr class='inp-divider'>", unsafe_allow_html=True)

                    # ── Section 2: Explicit Parameter Inputs ───────────────────────
                    st.markdown("<div class='inp-section-label'>⚙️ Explicit Parameter Inputs</div>", unsafe_allow_html=True)
                    if _inp_explicit_params:
                        _inp_pt_rows = "".join(
                            f"<tr><td class='inp-param-key'>{icon} {label}</td><td>{val[:120]}</td></tr>"
                            for label, icon, val in _inp_explicit_params
                        )
                        st.markdown(
                            f"<table class='inp-param-table'><thead><tr><th>Input Type</th><th>Value</th></tr></thead>"
                            f"<tbody>{_inp_pt_rows}</tbody></table>",
                            unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='inp-conn-none'>No explicit file, table, or query parameters found on this component.</div>", unsafe_allow_html=True)

                    st.markdown("<hr class='inp-divider'>", unsafe_allow_html=True)

                    # ── Section 3: Context Variable Inputs ────────────────────────
                    st.markdown("<div class='inp-section-label'>🌍 Context Variable Inputs</div>", unsafe_allow_html=True)
                    if _inp_ctx_refs:
                        _inp_ctx_html = "<div class='inp-conn-grid'>"
                        for _ctx in _inp_ctx_refs:
                            _inp_ctx_html += f"""<div class='inp-conn-card'>
                              <div class='inp-conn-type'>Context Variable</div>
                              <div class='inp-conn-name'>context.{_ctx}</div>
                              <div style='font-size:11px;color:#6b7280;margin-top:3px;'>Runtime-configurable input — value set per environment (Dev / Test / Prod)</div>
                            </div>"""
                        _inp_ctx_html += "</div>"
                        st.markdown(_inp_ctx_html, unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='inp-conn-none'>No <code>context.*</code> variable references detected in this component's code.</div>", unsafe_allow_html=True)

                    st.markdown("<hr class='inp-divider'>", unsafe_allow_html=True)

                    # ── Section 4: Code-Detected Implicit Sources ─────────────────
                    st.markdown("<div class='inp-section-label'>🔬 Code-Detected Implicit Input Sources</div>", unsafe_allow_html=True)
                    if _inp_code_sources:
                        _inp_cs_html = "<div class='inp-conn-grid'>"
                        for _cs_icon, _cs_name, _cs_desc, _cs_bg, _cs_col in _inp_code_sources:
                            _inp_cs_html += f"""<div class='inp-conn-card' style='border-left:4px solid {_cs_col};background:{_cs_bg};'>
                              <div class='inp-conn-type' style='color:{_cs_col};'>{_cs_icon} {_cs_name}</div>
                              <div style='font-size:12px;color:#4b5563;line-height:1.5;margin-top:4px;'>{_cs_desc}</div>
                            </div>"""
                        _inp_cs_html += "</div>"
                        st.markdown(_inp_cs_html, unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='inp-conn-none'>No implicit input sources detected in Java code patterns.</div>", unsafe_allow_html=True)

                    # ── Section 5: Routine / Library Inputs (if any) ──────────────
                    _inp_routine_refs_filtered = {k: v for k, v in _inp_routine_refs.items()
                                                  if k not in {"System", "String", "Integer", "Boolean", "Math", "Long", "Double"}}
                    if _inp_routine_refs_filtered or _comp.get("external_jars"):
                        st.markdown("<hr class='inp-divider'>", unsafe_allow_html=True)
                        st.markdown("<div class='inp-section-label'>📦 Routine & Library Inputs</div>", unsafe_allow_html=True)
                        _inp_rl_html = "<div class='inp-conn-grid'>"
                        for _rname, _rcnt in sorted(_inp_routine_refs_filtered.items(), key=lambda x: -x[1])[:8]:
                            _inp_rl_html += f"""<div class='inp-conn-card'>
                              <div class='inp-conn-type'>Custom Routine</div>
                              <div class='inp-conn-name'>{_rname}</div>
                              <div style='font-size:11px;color:#6b7280;margin-top:2px;'>Referenced ×{_rcnt} — provides helper functions or lookups used as input data</div>
                            </div>"""
                        for _ej in (_comp.get("external_jars") or [])[:6]:
                            _inp_rl_html += f"""<div class='inp-conn-card' style='border-left:4px solid #166534;background:#f0fdf4;'>
                              <div class='inp-conn-type' style='color:#166534;'>External JAR</div>
                              <div class='inp-conn-name' style='font-size:12px;'>{_ej}</div>
                              <div style='font-size:11px;color:#6b7280;margin-top:2px;'>Third-party library providing input processing or data access capability</div>
                            </div>"""
                        _inp_rl_html += "</div>"
                        st.markdown(_inp_rl_html, unsafe_allow_html=True)

                # Outputs ──────────────────────────────────────────────────────────
                with _jt_outputs:
                    st.markdown(f"#### Outputs — {_comp['uid']}")
                    st.caption("Everything this Java component produces or writes: downstream connections, write parameters, return variables, and code-detected output destinations.")

                    # ── CSS ────────────────────────────────────────────────────────
                    st.markdown("""
                    <style>
                    .out-section-label{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;margin-top:2px;}
                    .out-divider{border:none;border-top:1px solid #e4e3dc;margin:14px 0;}
                    .out-conn-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:8px;margin-bottom:4px;}
                    .out-conn-card{border:1px solid #e4e3dc;border-radius:10px;padding:11px 14px;background:#fff;}
                    .out-conn-card-active{border-color:#0f766e;background:#f0fdfa;}
                    .out-conn-type{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#8a8a85;margin-bottom:3px;}
                    .out-conn-name{font-size:13.5px;font-weight:700;color:#2d2d2a;margin-bottom:2px;}
                    .out-conn-ctype{font-size:11px;color:#6b7280;background:#f3f4f6;border-radius:4px;padding:1px 7px;display:inline-block;margin-bottom:3px;}
                    .out-conn-label{font-size:11px;color:#0f766e;font-weight:600;}
                    .out-conn-none{font-size:13px;color:#9ca3af;font-style:italic;padding:4px 0;}
                    .out-param-table{width:100%;border-collapse:collapse;font-size:12.5px;}
                    .out-param-table th{background:#0f766e;color:#fff;padding:7px 11px;text-align:left;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em;}
                    .out-param-table td{padding:7px 11px;border-bottom:1px solid #e4e3dc;color:#2d2d2a;vertical-align:top;}
                    .out-param-table tr:last-child td{border-bottom:none;}
                    .out-param-table tr:hover td{background:#f0fdfa;}
                    .out-param-key{font-weight:600;color:#0f766e;white-space:nowrap;}
                    .out-col-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px;margin-top:4px;}
                    .out-col-card{border:1px solid #e4e3dc;border-radius:7px;padding:7px 10px;background:#fff;}
                    .out-col-name{font-size:12px;font-weight:700;color:#2d2d2a;}
                    .out-col-type{font-size:11px;color:#0f766e;margin-top:1px;}
                    .out-summary-strip{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;}
                    .out-kpi{border:1px solid #e4e3dc;border-radius:9px;padding:9px 14px;background:#fff;min-width:110px;}
                    .out-kpi-label{font-size:10px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px;}
                    .out-kpi-value{font-size:22px;font-weight:800;color:#0f766e;line-height:1;}
                    .out-kpi-sub{font-size:11px;color:#8a8a85;margin-top:2px;}
                    .out-var-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:7px;margin-top:4px;}
                    .out-var-card{border:1px solid #e4e3dc;border-radius:8px;padding:8px 11px;background:#fff;}
                    .out-var-name{font-size:12.5px;font-weight:700;color:#2d2d2a;}
                    .out-var-type{font-size:11px;color:#7c3aed;background:#f5f3ff;border-radius:4px;padding:1px 6px;display:inline-block;margin-top:2px;}
                    .out-var-expl{font-size:11px;color:#6b7280;margin-top:3px;line-height:1.4;}
                    </style>""", unsafe_allow_html=True)

                    # ── Gather data ────────────────────────────────────────────────
                    _out_jd       = job.get("job_data", {})
                    _out_uid      = _comp["uid"]
                    _out_all_comp = {c.get("unique_name"): c for c in _out_jd.get("components", []) if isinstance(c, dict)}
                    _out_conns    = _out_jd.get("connections", [])
                    _out_code     = _comp.get("code", "")
                    _out_flags    = _comp["flags"]
                    _out_params   = _comp.get("parameters") or {}

                    # Downstream FLOW connections from this component
                    _out_flow_targets = [
                        conn for conn in _out_conns
                        if conn.get("source") == _out_uid
                        and conn.get("connector") in ("FLOW", "ITERATE", "REJECT", "MAIN", "FILTER_INNER_JOIN_REJECT")
                    ]
                    # All outgoing connections (including subjob triggers)
                    _out_all_targets = [
                        conn for conn in _out_conns
                        if conn.get("source") == _out_uid
                    ]
                    # Trigger-only (subjob sequencing) outgoing
                    _out_trigger_targets = [
                        conn for conn in _out_all_targets
                        if conn.get("connector") not in ("FLOW", "ITERATE", "REJECT", "MAIN", "FILTER_INNER_JOIN_REJECT")
                    ]

                    # Output parameters — write destinations configured on the component
                    _OUT_PARAM_KEYS = {
                        "FILE_NAME":      ("Output File Path",     "📄"),
                        "FILENAME":       ("Output File Path",     "📄"),
                        "TABLE":          ("Target DB Table",      "🗄️"),
                        "TABLE_NAME":     ("Target DB Table",      "🗄️"),
                        "DBTABLE":        ("Target DB Table",      "🗄️"),
                        "QUERY":          ("Write Query",          "🔍"),
                        "MEMO_SQL":       ("Write Query",          "🔍"),
                        "HOST":           ("Target DB Host",       "🌐"),
                        "DBNAME":         ("Target Database",      "🗄️"),
                        "POSTCODE":       ("Post-execution Code",  "⚙️"),
                        "END_CODE":       ("End Code",             "⚙️"),
                        "OUTPUT_STREAM":  ("Output Stream",        "📤"),
                    }
                    _out_explicit_params = [
                        (label, icon, _out_params[k].strip('"').strip("'"))
                        for k, (label, icon) in _OUT_PARAM_KEYS.items()
                        if _out_params.get(k, "").strip().strip('"').strip("'")
                    ]

                    # Variables assigned in code — detect assignment patterns like:
                    # String result = ..., int count = ..., globalMap.put(...), outputRow.*
                    _out_var_assignments = []
                    _seen_var_names = set()
                    _VAR_PATTERNS = [
                        # typed local variable declarations
                        (r'\b(String|int|long|double|float|boolean|Date|List|Map|Object|byte\[\])\s+(\w+)\s*=',
                         lambda m: (m.group(2), m.group(1), "Local variable — computed result passed to downstream row or used as output value")),
                        # globalMap assignments — Talend's cross-component output mechanism
                        (r'globalMap\.put\s*\(\s*"([^"]+)"',
                         lambda m: (f'globalMap["{m.group(1)}"]', "globalMap", "Global variable output — value is accessible by all downstream components in this job")),
                        # outputRow field assignments (tJavaRow)
                        (r'output_row\.(\w+)\s*=',
                         lambda m: (f"output_row.{m.group(1)}", "row field", "Output row field — written to the outgoing data row for the next component")),
                        # System.out / System.err
                        (r'System\.(out|err)\.print',
                         lambda m: (f"System.{m.group(1)}", "console", "Console output — writes a message to job execution logs")),
                    ]
                    for _vp_pattern, _vp_label_fn in _VAR_PATTERNS:
                        for _vm in re.finditer(_vp_pattern, _out_code):
                            try:
                                _vname, _vtype, _vexpl = _vp_label_fn(_vm)
                                if _vname not in _seen_var_names:
                                    _seen_var_names.add(_vname)
                                    _out_var_assignments.append({"name": _vname, "type": _vtype, "explanation": _vexpl})
                            except Exception:
                                logger.exception("Failed to parse Java variable assignment; skipping match.")
                                pass

                    # Code-detected write destinations from flags
                    _out_code_dests = []
                    if _out_flags.get("jdbc_calls"):
                        _out_code_dests.append(("🗄️", "Database (JDBC write)", "Writes or updates records in a database via direct JDBC — INSERT, UPDATE, or DELETE statements.", "#eff6ff", "#1d4ed8"))
                    if _out_flags.get("file_operations"):
                        _out_code_dests.append(("📄", "File System (write)", "Writes data to a local file path using Java I/O — FileOutputStream, PrintWriter, or FileWriter.", "#fffbeb", "#b45309"))
                    if _out_flags.get("runtime_exec"):
                        _out_code_dests.append(("⚙️", "External Process (output)", "Sends data to or triggers an OS-level process — output is consumed by an external program.", "#f5f3ff", "#7c3aed"))
                    if _out_flags.get("error_handling"):
                        _out_code_dests.append(("🚨", "Error / Reject Path", "Exceptions caught may route records to a reject link or write errors to a log / error table.", "#fff1f2", "#be123c"))
                    if any(kw in _out_code for kw in ("globalMap.put", "globalMap.get")):
                        _out_code_dests.append(("🌐", "Global Map", "Values written to globalMap are available as outputs to all subsequent components in the job.", "#f0fdfa", "#0f766e"))

                    # Downstream schema columns from target components
                    _out_downstream_cols = []
                    for _oconn in _out_flow_targets:
                        _otgt_uid  = _oconn.get("target", "")
                        _otgt_comp = _out_all_comp.get(_otgt_uid, {})
                        for _cpk, _cpv in (_otgt_comp.get("parameters") or {}).items():
                            if "SCHEMA" in _cpk.upper() and isinstance(_cpv, list):
                                for _col in _cpv:
                                    if isinstance(_col, dict) and _col.get("name"):
                                        _out_downstream_cols.append({
                                            "name": _col["name"],
                                            "type": _col.get("type", "Unknown"),
                                            "to":   _otgt_uid,
                                        })

                    # ── KPI strip ──────────────────────────────────────────────────
                    _out_kpi_html = "<div class='out-summary-strip'>"
                    _out_kpi_html += f"""<div class='out-kpi' style='border-left:4px solid #0f766e;'>
                      <div class='out-kpi-label'>Downstream Connections</div>
                      <div class='out-kpi-value'>{len(_out_flow_targets)}</div>
                      <div class='out-kpi-sub'>FLOW links out of this component</div>
                    </div>"""
                    _out_kpi_html += f"""<div class='out-kpi' style='border-left:4px solid #3C3489;'>
                      <div class='out-kpi-label'>Output Variables</div>
                      <div class='out-kpi-value'>{len(_out_var_assignments)}</div>
                      <div class='out-kpi-sub'>assignments detected in code</div>
                    </div>"""
                    _out_kpi_html += f"""<div class='out-kpi' style='border-left:4px solid #b45309;'>
                      <div class='out-kpi-label'>Write Parameters</div>
                      <div class='out-kpi-value'>{len(_out_explicit_params)}</div>
                      <div class='out-kpi-sub'>file / table / query outputs</div>
                    </div>"""
                    _out_kpi_html += f"""<div class='out-kpi' style='border-left:4px solid #7c3aed;'>
                      <div class='out-kpi-label'>Code-Detected Destinations</div>
                      <div class='out-kpi-value'>{len(_out_code_dests)}</div>
                      <div class='out-kpi-sub'>implicit write patterns</div>
                    </div>"""
                    if _out_trigger_targets:
                        _out_kpi_html += f"""<div class='out-kpi' style='border-left:4px solid #6b7280;'>
                          <div class='out-kpi-label'>Trigger Links</div>
                          <div class='out-kpi-value'>{len(_out_trigger_targets)}</div>
                          <div class='out-kpi-sub'>subjob sequencing only</div>
                        </div>"""
                    _out_kpi_html += "</div>"
                    st.markdown(_out_kpi_html, unsafe_allow_html=True)

                    # ── Section 1: Downstream Component Connections ────────────────
                    st.markdown("<div class='out-section-label'>🔗 Downstream Component Connections</div>", unsafe_allow_html=True)
                    if _out_flow_targets:
                        _out_conn_html = "<div class='out-conn-grid'>"
                        for _oconn in _out_flow_targets:
                            _otgt_uid   = _oconn.get("target", "")
                            _otgt_comp  = _out_all_comp.get(_otgt_uid, {})
                            _otgt_ctype = _otgt_comp.get("component_type", "Unknown")
                            _oconn_type = _oconn.get("connector", "FLOW")
                            _oconn_label = (
                                "Data row stream" if _oconn_type == "FLOW"    else
                                "Iterate trigger" if _oconn_type == "ITERATE" else
                                "Rejected records" if _oconn_type == "REJECT" else
                                "Filtered reject"  if "REJECT" in _oconn_type else
                                _oconn_type
                            )
                            # Destination hint from target parameters
                            _otgt_params = _otgt_comp.get("parameters", {})
                            _dest_hint = ""
                            for _dk in ("TABLE", "TABLE_NAME", "DBTABLE", "FILE_NAME", "FILENAME", "QUERY"):
                                _dv = _otgt_params.get(_dk, "").strip('"').strip("'")
                                if _dv:
                                    _dest_hint = f"Destination: {_dv[:40]}"
                                    break
                            _out_conn_html += f"""<div class='out-conn-card out-conn-card-active'>
                              <div class='out-conn-type'>{_oconn_type}</div>
                              <div class='out-conn-name'>{_otgt_uid}</div>
                              <div><span class='out-conn-ctype'>{_otgt_ctype}</span></div>
                              <div class='out-conn-label'>↳ {_oconn_label}</div>
                              {"<div style='font-size:11px;color:#6b7280;margin-top:3px;'>"+_dest_hint+"</div>" if _dest_hint else ""}
                            </div>"""
                        _out_conn_html += "</div>"
                        st.markdown(_out_conn_html, unsafe_allow_html=True)

                        if _out_downstream_cols:
                            st.markdown("**Downstream Schema Columns**")
                            _out_col_html = "<div class='out-col-grid'>"
                            for _ocol in _out_downstream_cols[:24]:
                                _out_col_html += f"""<div class='out-col-card'>
                                  <div class='out-col-name'>{_ocol['name']}</div>
                                  <div class='out-col-type'>{_ocol['type']}</div>
                                  <div style='font-size:10px;color:#9ca3af;'>to {_ocol['to']}</div>
                                </div>"""
                            if len(_out_downstream_cols) > 24:
                                _out_col_html += f"<div class='out-col-card' style='border-style:dashed;color:#9ca3af;font-size:12px;display:flex;align-items:center;justify-content:center;'>+{len(_out_downstream_cols)-24} more</div>"
                            _out_col_html += "</div>"
                            st.markdown(_out_col_html, unsafe_allow_html=True)
                    else:
                        if _out_trigger_targets:
                            st.markdown(
                                "<div class='out-conn-none'>No data-flow output connections detected. "
                                "This component passes control to the next subjob via sequencing triggers only — "
                                "its outputs are written directly to a destination (file, DB, globalMap) rather than passed as row data.</div>",
                                unsafe_allow_html=True)
                        else:
                            st.markdown("<div class='out-conn-none'>No downstream connections detected for this component.</div>", unsafe_allow_html=True)

                    # Trigger links (always shown if present, below the main section)
                    if _out_trigger_targets:
                        _out_trig_html = "<div style='margin-top:8px;'>"
                        for _otrig in _out_trigger_targets:
                            _otrig_tgt  = _otrig.get("target", "")
                            _otrig_comp = _out_all_comp.get(_otrig_tgt, {})
                            _otrig_ct   = _otrig_comp.get("component_type", "Unknown")
                            _otrig_type = _otrig.get("connector", "")
                            _out_trig_html += (
                                f"<span style='font-size:11px;color:#6b7280;background:#f3f4f6;"
                                f"border-radius:5px;padding:3px 9px;display:inline-block;margin:2px;'>"
                                f"⏭ {_otrig_type} → {_otrig_tgt} ({_otrig_ct})</span>"
                            )
                        _out_trig_html += "</div>"
                        st.markdown(_out_trig_html, unsafe_allow_html=True)

                    st.markdown("<hr class='out-divider'>", unsafe_allow_html=True)

                    # ── Section 2: Output Variables Detected in Code ───────────────
                    st.markdown("<div class='out-section-label'>📝 Output Variables Detected in Code</div>", unsafe_allow_html=True)
                    if _out_var_assignments:
                        _out_var_html = "<div class='out-var-grid'>"
                        for _ov in _out_var_assignments[:20]:
                            _out_var_html += f"""<div class='out-var-card'>
                              <div class='out-var-name'>{_ov['name']}</div>
                              <div><span class='out-var-type'>{_ov['type']}</span></div>
                              <div class='out-var-expl'>{_ov['explanation']}</div>
                            </div>"""
                        if len(_out_var_assignments) > 20:
                            _out_var_html += f"<div class='out-var-card' style='border-style:dashed;color:#9ca3af;font-size:12px;display:flex;align-items:center;justify-content:center;'>+{len(_out_var_assignments)-20} more</div>"
                        _out_var_html += "</div>"
                        st.markdown(_out_var_html, unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='out-conn-none'>No typed variable assignments, output_row fields, or globalMap writes detected in this component's code.</div>", unsafe_allow_html=True)

                    st.markdown("<hr class='out-divider'>", unsafe_allow_html=True)

                    # ── Section 3: Write Parameters ────────────────────────────────
                    st.markdown("<div class='out-section-label'>⚙️ Write / Destination Parameters</div>", unsafe_allow_html=True)
                    if _out_explicit_params:
                        _out_pt_rows = "".join(
                            f"<tr><td class='out-param-key'>{icon} {label}</td><td>{val[:120]}</td></tr>"
                            for label, icon, val in _out_explicit_params
                        )
                        st.markdown(
                            f"<table class='out-param-table'><thead><tr><th>Output Type</th><th>Value</th></tr></thead>"
                            f"<tbody>{_out_pt_rows}</tbody></table>",
                            unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='out-conn-none'>No explicit file, table, or query write parameters found on this component.</div>", unsafe_allow_html=True)

                    st.markdown("<hr class='out-divider'>", unsafe_allow_html=True)

                    # ── Section 4: Code-Detected Output Destinations ───────────────
                    st.markdown("<div class='out-section-label'>🔬 Code-Detected Output Destinations</div>", unsafe_allow_html=True)
                    if _out_code_dests:
                        _out_cd_html = "<div class='out-conn-grid'>"
                        for _cd_icon, _cd_name, _cd_desc, _cd_bg, _cd_col in _out_code_dests:
                            _out_cd_html += f"""<div class='out-conn-card' style='border-left:4px solid {_cd_col};background:{_cd_bg};'>
                              <div class='out-conn-type' style='color:{_cd_col};'>{_cd_icon} {_cd_name}</div>
                              <div style='font-size:12px;color:#4b5563;line-height:1.5;margin-top:4px;'>{_cd_desc}</div>
                            </div>"""
                        _out_cd_html += "</div>"
                        st.markdown(_out_cd_html, unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='out-conn-none'>No implicit write destinations detected in Java code patterns.</div>", unsafe_allow_html=True)

                # Process Flow ─────────────────────────────────────────────────────
                with _jt_flow:
                    st.markdown(f"#### Process Flow — {_comp['uid']}")
                    st.caption("Ordered business steps executed by this component. No technical code.")

                    _pf_flags = _comp["flags"]

                    # ── Ordered step catalogue (flag → step text) ─────────────────
                    # Steps are added in execution order: setup → input → validate → transform → output → error
                    _pf_step_catalogue = [
                        ("system_env",     "Read configuration settings and environment variables needed for processing"),
                        ("error_handling", "Initialise error handling to capture and log any failures during execution"),
                        ("file_operations","Open the required file or data source for reading"),
                        ("jdbc_calls",     "Connect to the database and prepare the data query"),
                        ("jdbc_calls",     "Execute the database query and retrieve the matching records"),
                        ("loops",          "Begin processing each record in the dataset one at a time"),
                        ("conditionals",   "Evaluate each record against the defined business conditions"),
                        ("string_manip",   "Clean and reformat text fields to meet the required standard"),
                        ("date_ops",       "Parse or reformat date and time values to the target format"),
                        ("math_ops",       "Calculate derived numeric values such as totals or scores"),
                        ("collections",    "Group or look up values using in-memory collections"),
                        ("external_jar",   "Apply processing logic from the external library"),
                        ("runtime_exec",   "Execute the required external system process and capture the result"),
                        ("loops",          "Continue to the next record and repeat until all records are processed"),
                        ("file_operations","Write the processed data to the output file or destination"),
                        ("jdbc_calls",     "Commit the database changes and close the connection"),
                        ("error_handling", "Handle any exceptions encountered and record them in the job log"),
                    ]

                    # Deduplicate while preserving order; cap at 15
                    _pf_seen_flags: dict[str, int] = {}
                    _pf_steps: list[str] = []
                    for _pf_flag, _pf_text in _pf_step_catalogue:
                        if not _pf_flags.get(_pf_flag):
                            continue
                        _pf_seen_flags[_pf_flag] = _pf_seen_flags.get(_pf_flag, 0) + 1
                        # Allow at most 2 occurrences per flag (e.g. open + close jdbc)
                        if _pf_seen_flags[_pf_flag] > 2:
                            continue
                        _pf_steps.append(_pf_text)
                        if len(_pf_steps) == 15:
                            break

                    if not _pf_steps:
                        _pf_steps = ["Receive input data from the upstream pipeline component",
                                     "Apply custom processing logic to each record",
                                     "Pass the processed records to the next step in the pipeline"]

                    _pf_css = """
                    <style>
                    .pf-list{list-style:none;margin:0;padding:0;}
                    .pf-list li{display:flex;align-items:flex-start;gap:12px;padding:9px 14px;border-bottom:1px solid #e4e3dc;font-size:13px;color:#2d2d2a;line-height:1.55;}
                    .pf-list li:last-child{border-bottom:none;}
                    .pf-list li:hover{background:#f5f4f0;}
                    .pf-num{min-width:24px;height:24px;border-radius:50%;background:#3C3489;color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;}
                    </style>"""
                    st.markdown(_pf_css, unsafe_allow_html=True)

                    _pf_items = "".join(
                        f"<li><span class='pf-num'>{i+1}</span><span>{step}</span></li>"
                        for i, step in enumerate(_pf_steps)
                    )
                    st.markdown(f"<ul class='pf-list'>{_pf_items}</ul>", unsafe_allow_html=True)

                # Migration Impact ──────────────────────────────────────────────────
                with _jt_risk:
                    st.markdown(f"#### Migration Impact — {_comp['uid']}")
                    st.caption(f"`{_comp['component_type']}` · {_comp['loc']} lines of custom Java")

                    _risk = _comp["risk"]
                    _cx   = _comp["complexity"]
                    _mf   = _comp["flags"]

                    # ── Colour helpers ─────────────────────────────────────────────
                    _RISK_COLOR  = {"CRITICAL": "#be123c", "HIGH": "#c2500a", "MEDIUM": "#1d4ed8", "LOW": "#166534"}
                    _RISK_BG     = {"CRITICAL": "#fff1f2", "HIGH": "#fff7ed", "MEDIUM": "#eff6ff", "LOW": "#f0fdf4"}
                    _RISK_ICON   = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
                    _USE_COLOR   = {"Yes": "#166534", "No": "#6b7280"}
                    _USE_BG      = {"Yes": "#f0fdf4", "No": "#f9fafb"}

                    # ── Derive usage flags ─────────────────────────────────────────
                    _mi_db       = "Yes" if _mf.get("jdbc_calls")      else "No"
                    _mi_file     = "Yes" if _mf.get("file_operations")  else "No"
                    _mi_api      = "Yes" if _mf.get("runtime_exec")     else "No"
                    _mi_code     = "Yes" if _comp["loc"] > 0            else "No"

                    # ── Recommendation ────────────────────────────────────────────
                    _mi_rec_map = {
                        "CRITICAL": "Requires manual rewrite before migration. Runtime execution and OS-level calls are blocked in cloud environments. Engage a developer to replace this logic with supported Talend components.",
                        "HIGH":     "Requires manual review and likely refactoring. File or environment access must be replaced with cloud-compatible patterns before migrating.",
                        "MEDIUM":   "Can migrate with targeted changes. Review JDBC calls and external library dependencies to ensure compatibility with the target environment.",
                        "LOW":      "Suitable for migration with standard process. Verify output behaviour in a test environment before promoting to production.",
                    }
                    _mi_rec = _mi_rec_map.get(_risk["overall"], "Review component logic before migration.")

                    # ── CSS ────────────────────────────────────────────────────────
                    _mi_css = """
                    <style>
                    .mi-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;}
                    .mi-card{border:1px solid #e4e3dc;border-radius:10px;padding:12px 14px;}
                    .mi-card-label{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px;}
                    .mi-card-value{font-size:20px;font-weight:800;line-height:1.1;}
                    .mi-card-sub{font-size:11px;color:#8a8a85;margin-top:3px;}
                    .mi-use-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px;}
                    .mi-use-card{border:1px solid #e4e3dc;border-radius:10px;padding:10px 12px;text-align:center;}
                    .mi-use-label{font-size:11px;font-weight:600;color:#8a8a85;text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px;}
                    .mi-use-value{font-size:15px;font-weight:800;}
                    .mi-rec{border-radius:10px;padding:12px 16px;margin-bottom:10px;}
                    .mi-rec-label{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px;}
                    .mi-rec-text{font-size:13px;line-height:1.6;}
                    .mi-findings{margin-top:12px;}
                    .mi-finding-row{display:flex;align-items:flex-start;gap:10px;padding:7px 0;border-bottom:1px solid #e4e3dc;font-size:13px;color:#2d2d2a;line-height:1.5;}
                    .mi-finding-row:last-child{border-bottom:none;}
                    .mi-finding-badge{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;white-space:nowrap;flex-shrink:0;margin-top:2px;}
                    </style>"""
                    st.markdown(_mi_css, unsafe_allow_html=True)

                    # ── Row 1: Complexity | Risk | Custom Code ─────────────────────
                    _cx_color = _RISK_COLOR.get(_cx["label"], "#374151")
                    _cx_bg    = _RISK_BG.get(_cx["label"], "#f9fafb")
                    _rv_color = _RISK_COLOR.get(_risk["overall"], "#374151")
                    _rv_bg    = _RISK_BG.get(_risk["overall"], "#f9fafb")
                    st.markdown(f"""
                    <div class="mi-grid">
                      <div class="mi-card" style="border-left:4px solid {_cx_color};background:{_cx_bg};">
                        <div class="mi-card-label">Complexity</div>
                        <div class="mi-card-value" style="color:{_cx_color};">{_cx["label"]}</div>
                        <div class="mi-card-sub">Status: {_cx["label"]}</div>
                      </div>
                      <div class="mi-card" style="border-left:4px solid {_rv_color};background:{_rv_bg};">
                        <div class="mi-card-label">Overall Risk</div>
                        <div class="mi-card-value" style="color:{_rv_color};">{_RISK_ICON.get(_risk["overall"],"⚪")} {_risk["overall"]}</div>
                        <div class="mi-card-sub">{len(_risk["findings"])} finding(s) detected</div>
                      </div>
                      <div class="mi-card" style="border-left:4px solid #3C3489;background:#f5f4ff;">
                        <div class="mi-card-label">Custom Code</div>
                        <div class="mi-card-value" style="color:#3C3489;">{_comp["loc"]} lines</div>
                        <div class="mi-card-sub">{_comp["component_type"]}</div>
                      </div>
                    </div>""", unsafe_allow_html=True)

                    # ── Row 2: DB | File | API | External JARs ────────────────────
                    _mi_jars = str(len(_comp["external_jars"])) if _comp["external_jars"] else "0"
                    _mi_jar_col = _USE_COLOR["Yes"] if _comp["external_jars"] else _USE_COLOR["No"]
                    _mi_jar_bg  = _USE_BG["Yes"]    if _comp["external_jars"] else _USE_BG["No"]
                    st.markdown(f"""
                    <div class="mi-use-grid">
                      <div class="mi-use-card" style="background:{_USE_BG[_mi_db]};">
                        <div class="mi-use-label">DB Usage</div>
                        <div class="mi-use-value" style="color:{_USE_COLOR[_mi_db]};">{_mi_db}</div>
                      </div>
                      <div class="mi-use-card" style="background:{_USE_BG[_mi_file]};">
                        <div class="mi-use-label">File Usage</div>
                        <div class="mi-use-value" style="color:{_USE_COLOR[_mi_file]};">{_mi_file}</div>
                      </div>
                      <div class="mi-use-card" style="background:{_USE_BG[_mi_api]};">
                        <div class="mi-use-label">API / OS Usage</div>
                        <div class="mi-use-value" style="color:{_USE_COLOR[_mi_api]};">{_mi_api}</div>
                      </div>
                      <div class="mi-use-card" style="background:{_mi_jar_bg};">
                        <div class="mi-use-label">External JARs</div>
                        <div class="mi-use-value" style="color:{_mi_jar_col};">{_mi_jars}</div>
                      </div>
                    </div>""", unsafe_allow_html=True)

                    # ── Recommendation ────────────────────────────────────────────
                    _rec_color = _RISK_COLOR.get(_risk["overall"], "#374151")
                    _rec_bg    = _RISK_BG.get(_risk["overall"], "#f9fafb")
                    st.markdown(f"""
                    <div class="mi-rec" style="background:{_rec_bg};border-left:4px solid {_rec_color};">
                      <div class="mi-rec-label">💡 Recommendation</div>
                      <div class="mi-rec-text">{_mi_rec}</div>
                    </div>""", unsafe_allow_html=True)

                    # ── Risk Findings ─────────────────────────────────────────────
                    st.markdown("<div class='mi-findings'>", unsafe_allow_html=True)
                    st.markdown("**Risk Findings**")
                    _finding_rows = ""
                    for _finding in _risk["findings"]:
                        _fc = _RISK_COLOR.get(_finding["risk"], "#374151")
                        _fb = _RISK_BG.get(_finding["risk"], "#f9fafb")
                        _finding_rows += (
                            f"<div class='mi-finding-row'>"
                            f"<span class='mi-finding-badge' style='background:{_fb};color:{_fc};'>{_finding['risk']}</span>"
                            f"<span>{_finding['reason']}</span></div>"
                        )
                    st.markdown(_finding_rows + "</div>", unsafe_allow_html=True)

                # Dependencies ─────────────────────────────────────────────────────
                with _jt_deps:
                    st.markdown(f"#### Dependencies — {job_name}")
                    st.caption("Dependency groups detected across all Java components in this job.")
                    _graph_nodes = _jl["graph_nodes"]
                    _graph_edges = _jl["graph_edges"]

                    # ── Build grouped dependency data from existing analysis ────────
                    _dep_flags = _comp["flags"]

                    _dep_groups = {
                        "Database":   {"icon": "🗄️",  "color": "#1d4ed8", "bg": "#eff6ff", "items": []},
                        "Files":      {"icon": "📁",  "color": "#b45309", "bg": "#fffbeb", "items": []},
                        "APIs":       {"icon": "🔌",  "color": "#7c3aed", "bg": "#f5f3ff", "items": []},
                        "Components": {"icon": "☕",  "color": "#3C3489", "bg": "#f5f4ff", "items": []},
                        "Libraries":  {"icon": "📦",  "color": "#166534", "bg": "#f0fdf4", "items": []},
                        "Context":    {"icon": "⚙️",  "color": "#0f766e", "bg": "#f0fdfa", "items": []},
                    }

                    if _dep_flags.get("jdbc_calls"):
                        _dep_groups["Database"]["items"].append("JDBC database connection")
                    for _edge_src, _edge_tgt in _graph_edges:
                        if "DB" in _edge_tgt or "JDBC" in _edge_tgt:
                            if _edge_tgt not in _dep_groups["Database"]["items"]:
                                _dep_groups["Database"]["items"].append(_edge_tgt)

                    if _dep_flags.get("file_operations"):
                        _dep_groups["Files"]["items"].append("Local file system access")

                    if _dep_flags.get("runtime_exec"):
                        _dep_groups["APIs"]["items"].append("OS process / Runtime execution")
                    if _dep_flags.get("system_env"):
                        _dep_groups["APIs"]["items"].append("System environment variables")

                    for _jl_comp_item in _jl_comps:
                        _dep_groups["Components"]["items"].append(
                            f"{_jl_comp_item['uid']} ({_jl_comp_item['component_type']})"
                        )

                    for _ej in _jl["external_jars"]:
                        _dep_groups["Libraries"]["items"].append(_ej)
                    for _rn, _rc in sorted(_jl["routine_usage"].items(), key=lambda x: -x[1]):
                        _dep_groups["Libraries"]["items"].append(f"{_rn} (routine ×{_rc})")

                    if _dep_flags.get("system_env"):
                        _dep_groups["Context"]["items"].append("JVM system properties")
                    for _ctx_node in _graph_nodes:
                        if "context" in _ctx_node.lower() or "ctx" in _ctx_node.lower():
                            if _ctx_node not in _dep_groups["Context"]["items"]:
                                _dep_groups["Context"]["items"].append(_ctx_node)

                    # ── CSS ────────────────────────────────────────────────────────
                    _dep_css = """
                    <style>
                    .dep-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;}
                    .dep-card{border:1px solid #e4e3dc;border-radius:10px;padding:12px 14px;}
                    .dep-card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}
                    .dep-card-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;}
                    .dep-card-count{font-size:18px;font-weight:800;}
                    .dep-card-items{font-size:12px;color:#6b7280;line-height:1.7;}
                    .dep-card-item{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
                    .dep-none{font-size:12px;color:#9ca3af;font-style:italic;}
                    </style>"""
                    st.markdown(_dep_css, unsafe_allow_html=True)

                    # ── Render group cards ─────────────────────────────────────────
                    _dep_card_html = "<div class='dep-grid'>"
                    for _grp_name, _grp in _dep_groups.items():
                        _cnt = len(_grp["items"])
                        _item_html = "".join(
                            f"<span class='dep-card-item'>• {i}</span>"
                            for i in _grp["items"][:4]
                        )
                        if _cnt > 4:
                            _item_html += f"<span class='dep-card-item dep-none'>+{_cnt - 4} more</span>"
                        if not _grp["items"]:
                            _item_html = "<span class='dep-none'>None detected</span>"
                        _dep_card_html += f"""
                        <div class='dep-card' style='border-left:4px solid {_grp["color"]};background:{_grp["bg"]};'>
                          <div class='dep-card-header'>
                            <span class='dep-card-title' style='color:{_grp["color"]};'>{_grp["icon"]} {_grp_name}</span>
                            <span class='dep-card-count' style='color:{_grp["color"]};'>{_cnt}</span>
                          </div>
                          <div class='dep-card-items'>{_item_html}</div>
                        </div>"""
                    _dep_card_html += "</div>"
                    st.markdown(_dep_card_html, unsafe_allow_html=True)

                    # ── Dependency graph (kept as-is) ──────────────────────────────
                    if _graph_nodes and _graph_edges:
                        st.markdown("**Dependency Graph**")
                        def _safe_nid(s: str) -> str:
                            return re.sub(r"[^A-Za-z0-9_]", "_", s)

                        _dep_lines = ["graph LR"]
                        for _n in _graph_nodes:
                            _nid = _safe_nid(_n)
                            _icon = "☕" if _n in [c["uid"] for c in _jl_comps] else "📦"
                            _dep_lines.append(f'    {_nid}["{_icon} {_n}"]')
                        for _src, _tgt in _graph_edges:
                            _dep_lines.append(f"    {_safe_nid(_src)} --> {_safe_nid(_tgt)}")
                        _render_mermaid("\n".join(_dep_lines), height=320)
                    else:
                        st.info("No dependency graph edges detected in Java components.")

            # ── All-job Java summary (outside component selector) ──────────────────
            with st.expander("📊 Repository Java Summary", expanded=False):
                _all_java_jobs = [
                    j for j in all_jobs
                    if any(c.get("component_type") in {"tJava", "tJavaRow", "tJavaFlex"}
                           for c in j["job_data"].get("components", []))
                ]
                if _all_java_jobs:
                    _RS_RISK_C = {"CRITICAL": "#be123c", "HIGH": "#c2500a", "MEDIUM": "#1d4ed8", "LOW": "#166534"}
                    _RS_RISK_B = {"CRITICAL": "#fff1f2", "HIGH": "#fff7ed", "MEDIUM": "#eff6ff", "LOW": "#f0fdf4"}
                    st.markdown("""
                    <style>
                    .rs-table{width:100%;border-collapse:collapse;font-size:13px;}
                    .rs-table th{background:#f5f4f0;color:#8a8a85;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;padding:8px 12px;text-align:left;border-bottom:2px solid #e4e3dc;}
                    .rs-table td{padding:9px 12px;border-bottom:1px solid #f0efe8;vertical-align:middle;color:#2d2d2a;}
                    .rs-table tr:last-child td{border-bottom:none;}
                    .rs-table tr:hover td{background:#fafaf7;}
                    .rs-badge{display:inline-block;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;}
                    .rs-num{font-variant-numeric:tabular-nums;font-weight:600;}
                    </style>""", unsafe_allow_html=True)
                    _rs_rows = ""
                    for _jj in _all_java_jobs:
                        _jjl_key = f"_java_logic_{_jj['job_data']['job_name']}"
                        if _jjl_key not in st.session_state:
                            st.session_state[_jjl_key] = analyze_java_logic(_jj)
                        _jjl = st.session_state[_jjl_key]
                        _rr = _jjl["overall_risk"]
                        _rc = _RS_RISK_C.get(_rr, "#374151")
                        _rb = _RS_RISK_B.get(_rr, "#f9fafb")
                        _jar_flag = "⚠️ " if len(_jjl["external_jars"]) > 0 else ""
                        _rs_rows += (
                            f"<tr>"
                            f"<td><strong>{_jjl['job_name']}</strong></td>"
                            f"<td class='rs-num'>{_jjl['java_component_count']}</td>"
                            f"<td class='rs-num'>{_jjl['total_loc']}</td>"
                            f"<td class='rs-num'>{_jjl['max_complexity_score']}</td>"
                            f"<td><span class='rs-badge' style='color:{_rc};background:{_rb};'>{_rr}</span></td>"
                            f"<td class='rs-num'>{_jar_flag}{len(_jjl['external_jars'])}</td>"
                            f"</tr>"
                        )
                    st.markdown(
                        f"<table class='rs-table'><thead><tr>"
                        f"<th>Job</th><th>Components</th><th>LOC</th><th>Complexity</th><th>Risk</th><th>JARs</th>"
                        f"</tr></thead><tbody>{_rs_rows}</tbody></table>",
                        unsafe_allow_html=True)
                else:
                    st.info("No Java components found across loaded jobs.")


    if _cat_sel == "Documentation":
        _doc_summary, _doc_tdd, _doc_hub, _doc_testing = st.tabs(["Documentation Summary", "TDD", "Docs Hub", "Testing"])
        with _doc_summary:
            _render_documentation_summary(job, jd, _inv, _all_recs, _sql_ops, job_name)

        with _doc_tdd:
            _render_tdd_tab_content()

        # ── Documentation Hub Tab ──────────────────────────────────────────────────
        with _doc_hub:
            _render_docs_hub_tab_content()

        with _doc_testing:
            import app.ui.tdd_page as _tdd_mod
            _tdd_mod._KEY_CTX = "_j360_doc_testing"
            from app.ui.tdd_page import _render_testing_section
            _render_testing_section()


    if _cat_sel == "Export Center":
        _xp_tab, = st.tabs(["Export Reports"])
        with _xp_tab:
            _render_phase8_export_center(job, jd, _inv, _all_recs, _sql_ops, job_name, _cached)
