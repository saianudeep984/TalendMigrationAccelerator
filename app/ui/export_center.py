"""
TMA Documentation Export Center
================================

Enterprise-grade Export Center for the TMA Documentation Hub. Provides four
export modes (current document, selected sections, multiple documents,
complete documentation package) across four output formats (PDF, HTML, DOCX,
ZIP package).

Built on top of the existing TMA report-generation framework — every document
is produced through the project's canonical generators rather than recreated
locally:

    * TDD                  → app.tiap.documentation.tdd_export
    * LLD                  → app.tiap.documentation.functional_doc_generator
                              + technical_doc_generator + tdd_sections
    * Migration Runbook    → app.ui.migration_runbook_dashboard.export_runbook
    * Executive Report     → app.ui.dashboard._exec_*  + report_pack_generator
    * Architecture Report  → app.ui.architecture_intelligence_dashboard.export_*
    * Validation Report    → app.tiap.testing.validation_framework
    * Migration Report     → app.ui.migration_intelligence_dashboard.export_*

PDF / DOCX / HTML are produced through the unified writer functions in
`report_pack_generator` (DOCX/HTML/PDF) and `export_utils.write_pdf` /
`write_docx` / `markdown_to_html` so output styling stays consistent with
the rest of the application.

ZIP packaging uses the standard library `zipfile`.

This module is idempotent — multiple reruns of the page never reset user
selections (everything is persisted under `st.session_state["ec2_*"]`).
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from app.ui.design_system_v2 import empty_state_card, section_header
from app.utils.safe_access import safe_get


# ── Constants ─────────────────────────────────────────────────────────────────

EC_MODE_CURRENT  = "Export Current Document"
EC_MODE_SECTIONS = "Export Selected Sections"
EC_MODE_MULTI    = "Export Multiple Documents"
EC_MODE_PACKAGE  = "Export Complete Documentation Package"

EC_MODES = [EC_MODE_CURRENT, EC_MODE_SECTIONS, EC_MODE_MULTI, EC_MODE_PACKAGE]

FORMAT_PDF  = "PDF"
FORMAT_HTML = "HTML"
FORMAT_DOCX = "DOCX"
FORMAT_ZIP  = "ZIP Package"

# Format options offered for each export mode.
MODE_FORMATS = {
    EC_MODE_CURRENT:  [FORMAT_PDF, FORMAT_HTML, FORMAT_DOCX],
    EC_MODE_SECTIONS: [FORMAT_PDF, FORMAT_HTML, FORMAT_DOCX],
    EC_MODE_MULTI:    [FORMAT_PDF, FORMAT_HTML, FORMAT_DOCX, FORMAT_ZIP],
    EC_MODE_PACKAGE:  [FORMAT_ZIP],
}

# Document types supported. New types can be added here without touching the
# rest of the Export Center logic — registration is data-driven.
DOC_TDD       = "TDD"
DOC_LLD       = "LLD"
DOC_RUNBOOK   = "Migration Runbook"
DOC_EXEC      = "Executive Report"
DOC_ARCH      = "Architecture Report"
DOC_VALID     = "Validation Report"
DOC_MIGRATION = "Migration Report"

ALL_DOCUMENTS = [
    DOC_TDD, DOC_LLD, DOC_RUNBOOK, DOC_EXEC, DOC_ARCH, DOC_VALID, DOC_MIGRATION,
]

# Default sections per document type. Used by "Export Selected Sections" and
# the section selector UI. Generators are free to add or skip sections at
# build time — these are *display* names.
DOC_SECTIONS: Dict[str, List[str]] = {
    DOC_TDD: [
        "Executive Summary", "Repository Overview", "Inventory Analysis",
        "Complexity Analysis", "Risk Assessment", "Dependency Analysis",
        "Migration Readiness", "Job Analysis", "Column Mapping",
        "Data Lineage", "Migration Recommendations", "Testing Summary",
        "Appendices",
    ],
    DOC_LLD: [
        "Executive Summary", "Component Inventory", "Job Specifications",
        "Column Mapping", "Data Lineage", "Schema Definitions",
        "Configuration Details", "Appendices",
    ],
    DOC_RUNBOOK: [
        "Overview", "Pre-Migration Checklist", "Cutover Plan",
        "Validation Steps", "Rollback Plan", "Post-Migration Tasks",
        "Communication Plan", "Appendices",
    ],
    DOC_EXEC: [
        "Executive Summary", "Cost Analysis", "Timeline",
        "Resource Plan", "KPIs", "Risk Profile", "Roadmap",
        "Migration Assessment",
    ],
    DOC_ARCH: [
        "Architecture Overview", "Auto-Fix Recommendations",
        "Cloud Readiness", "Infrastructure", "Integration Map",
        "Risk & Compliance", "Appendices",
    ],
    DOC_VALID: [
        "Validation Strategy", "Test Coverage", "Validation Results",
        "Quality Gates", "Defects Summary", "Sign-off",
    ],
    DOC_MIGRATION: [
        "Migration Intelligence", "Impact Intelligence",
        "Readiness Score", "Wave Planning", "Recommendations",
    ],
}


# ── Session-state helpers (persistent selections) ─────────────────────────────

_SS_MODE     = "ec2_mode"
_SS_CURRENT  = "ec2_current_doc"
_SS_DOCS     = "ec2_selected_docs"
_SS_SECTIONS = "ec2_selected_sections"   # dict[doc_type] -> list[str]
_SS_FORMAT   = "ec2_format"


def _init_state() -> None:
    if _SS_MODE not in st.session_state:
        st.session_state[_SS_MODE] = EC_MODE_CURRENT
    if _SS_CURRENT not in st.session_state:
        st.session_state[_SS_CURRENT] = DOC_TDD
    if _SS_DOCS not in st.session_state:
        st.session_state[_SS_DOCS] = list(ALL_DOCUMENTS)
    if _SS_SECTIONS not in st.session_state:
        st.session_state[_SS_SECTIONS] = {d: list(s) for d, s in DOC_SECTIONS.items()}
    if _SS_FORMAT not in st.session_state:
        st.session_state[_SS_FORMAT] = FORMAT_PDF


# ── Section content builders (wrap existing generators) ──────────────────────

def _md_table(rows: List[Dict[str, Any]], headers: List[str]) -> str:
    if not rows:
        return ""
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")
    return "\n".join(out)


def _exec_sections() -> Dict[str, str]:
    """Build markdown sections for the Executive Report."""
    from app.ui.dashboard import (
        _exec_business_model, _exec_summary_df, _exec_cost_df,
        _exec_timeline_df, _exec_resource_df, _exec_roadmap_df,
    )
    from app.ui.export_assets import asset_image_md

    jobs       = st.session_state.get("last_analysis_jobs", []) or []
    readiness  = st.session_state.get("readiness_score", {})
    effort     = st.session_state.get("effort_estimate", {})
    routines   = st.session_state.get("routine_analysis", {})
    joblets    = st.session_state.get("joblet_analysis", {})
    deprecated = st.session_state.get("deprecated_rows", [])
    custom     = st.session_state.get("custom_analysis", {})

    if not jobs:
        return {"Executive Summary": "_No repository loaded — run analysis first._"}

    m = _exec_business_model(jobs, readiness, effort, routines, joblets, deprecated, custom)

    summary_md  = _md_table(_exec_summary_df(m).to_dict("records"),  ["Metric", "Value"])
    cost_md     = _md_table(_exec_cost_df(m).to_dict("records"),     ["Category", "Estimated Cost"])
    timeline_md = _md_table(_exec_timeline_df(m).to_dict("records"), ["Milestone", "Duration"])
    resource_md = _md_table(_exec_resource_df(m).to_dict("records"), ["Role", "Estimate"])
    roadmap_md  = _md_table(_exec_roadmap_df(m).to_dict("records"),  ["Phase", "Outcome", "Status"])

    risk_label  = safe_get(m, "risk_label", "LOW") or "LOW"
    high_risk   = safe_get(m, "high_risk", 0)
    health      = safe_get(m, "health", 0)
    success     = safe_get(m, "success_rate", 0)
    kpi_md      = _md_table(
        [
            {"Metric": "Total Jobs", "Value": safe_get(m, "total_jobs", 0)},
            {"Metric": "Migration Ready Jobs", "Value": safe_get(m, "ready_jobs", 0)},
            {"Metric": "High Risk Jobs", "Value": high_risk},
            {"Metric": "Unsupported Components", "Value": safe_get(m, "unsupported", 0)},
            {"Metric": "Estimated Migration Success Rate", "Value": f"{success}%"},
            {"Metric": "Repository Health Score", "Value": f"{health}%"},
        ],
        ["Metric", "Value"],
    )
    risk_md = (
        f"**Risk Label:** {risk_label}\n\n"
        f"**High / Critical Risk Findings:** {high_risk}\n\n"
        f"**Repository Health Score:** {health}%\n\n"
        f"**Estimated Migration Success Rate:** {success}%\n"
    )

    # Embed the visuals built by export_assets.collect_for_doc.
    kpi_chart_md = "\n\n" + asset_image_md("Executive_KPIs", "Executive KPIs")
    cmpx_chart_md = "\n\n" + asset_image_md("Complexity_Distribution", "Complexity Distribution")
    rag_chart_md  = "\n\n" + asset_image_md("Readiness_RAG", "Readiness RAG")

    return {
        "Executive Summary":      f"# Executive Summary\n\n{summary_md}{kpi_chart_md}",
        "Cost Analysis":          f"# Cost Analysis\n\n{cost_md}",
        "Timeline":               f"# Timeline\n\n{timeline_md}",
        "Resource Plan":          f"# Resource Plan\n\n{resource_md}",
        "KPIs":                   f"# KPIs\n\n{kpi_md}{cmpx_chart_md}{rag_chart_md}",
        "Risk Profile":           f"# Risk Profile\n\n{risk_md}{rag_chart_md}",
        "Roadmap":                f"# Roadmap\n\n{roadmap_md}",
        "Migration Assessment":   f"# Migration Assessment\n\n{summary_md}\n\n{kpi_md}{kpi_chart_md}",
    }


def _tdd_sections() -> Dict[str, str]:
    """Build TDD markdown sections via existing generators."""
    jobs = st.session_state.get("last_analysis_jobs", []) or []
    if not jobs:
        return {"Executive Summary": "_No repository loaded — run analysis first._"}

    repository_path = st.session_state.get("last_repo_path")
    effort = st.session_state.get("effort_estimate", {})

    sections: Dict[str, str] = {}
    try:
        from app.tiap.documentation.executive_summary_generator import ExecutiveSummaryGenerator
        sections["Executive Summary"] = ExecutiveSummaryGenerator().generate(jobs, repository_path, effort)
    except Exception as e:  # pragma: no cover - generator robustness
        sections["Executive Summary"] = f"_Executive Summary unavailable: {e}_"

    try:
        from app.tiap.documentation.report_pack_generator import (
            _build_repository_overview_model, _repository_overview_section,
        )
        ov = _build_repository_overview_model(jobs, repository_path)
        sections["Repository Overview"] = _repository_overview_section(ov)
    except Exception as e:
        sections["Repository Overview"] = f"_Repository Overview unavailable: {e}_"

    try:
        from app.tiap.inventory.inventory_parser import InventoryParser
        inv = InventoryParser().build_inventory(jobs, repository_path)
        kpis = inv.get("kpis", {})
        sections["Inventory Analysis"] = (
            "# Inventory Analysis\n\n"
            + _md_table([{"Metric": k, "Value": v} for k, v in kpis.items()], ["Metric", "Value"])
        )
    except Exception as e:
        sections["Inventory Analysis"] = f"_Inventory Analysis unavailable: {e}_"

    try:
        from app.tiap.documentation.report_pack_generator import _routine_assessment_md
        sections["Complexity Analysis"] = _routine_assessment_md(jobs)
    except Exception as e:
        sections["Complexity Analysis"] = f"_Complexity Analysis unavailable: {e}_"

    try:
        from app.tiap.documentation.report_pack_generator import _java_risk_md
        sections["Risk Assessment"] = _java_risk_md(jobs)
    except Exception as e:
        sections["Risk Assessment"] = f"_Risk Assessment unavailable: {e}_"

    try:
        from app.tiap.documentation.report_pack_generator import _impact_lineage_section
        sections["Dependency Analysis"] = _impact_lineage_section(jobs)
    except Exception as e:
        sections["Dependency Analysis"] = f"_Dependency Analysis unavailable: {e}_"

    try:
        from app.tiap.documentation.report_pack_generator import _readiness_scores
        sections["Migration Readiness"] = _readiness_scores(jobs, repository_path)
    except Exception as e:
        sections["Migration Readiness"] = f"_Migration Readiness unavailable: {e}_"

    try:
        from app.tiap.documentation.technical_doc_generator import TechnicalDocGenerator
        sections["Job Analysis"] = TechnicalDocGenerator().generate(
            jobs, repository_path, st.session_state.get("technical_doc_template")
        )
    except Exception as e:
        sections["Job Analysis"] = f"_Job Analysis unavailable: {e}_"

    try:
        rows = []
        for j in jobs:
            jname = j.get("job_data", {}).get("job_name", "Unknown")
            for c in j.get("job_data", {}).get("columns", []) or []:
                rows.append({
                    "Job": jname,
                    "Source": c.get("source", ""),
                    "Target": c.get("target", ""),
                    "Type": c.get("data_type", ""),
                })
        sections["Column Mapping"] = (
            "# Column Mapping\n\n" + (_md_table(rows, ["Job", "Source", "Target", "Type"]) if rows else "_No column mappings detected._")
        )
    except Exception as e:
        sections["Column Mapping"] = f"_Column Mapping unavailable: {e}_"

    try:
        from app.tiap.graph.flowchart_generator import FlowchartGenerator
        from app.ui.export_assets import asset_image_md
        flows = FlowchartGenerator().generate(jobs)
        sections["Data Lineage"] = (
            "# Data Lineage\n\n"
            + asset_image_md("Data_Lineage", "Data Lineage")
            + "\n\n"
            + asset_image_md("TDD_technical_flow", "Technical Flow")
            + "\n\n```mermaid\n"
            + str(flows.get("technical_flow", "")) + "\n```\n"
        )
    except Exception as e:
        sections["Data Lineage"] = f"_Data Lineage unavailable: {e}_"

    try:
        from app.tiap.documentation.report_pack_generator import _recommendations
        sections["Migration Recommendations"] = _recommendations(jobs, st.session_state.get("auto_fix_recs"))
    except Exception as e:
        sections["Migration Recommendations"] = f"_Migration Recommendations unavailable: {e}_"

    try:
        from app.tiap.testing.test_case_generator import generate_test_cases  # type: ignore
        sections["Testing Summary"] = generate_test_cases(jobs) or "_No test cases generated._"
    except Exception:
        # Fallback: cheap summary
        sections["Testing Summary"] = "# Testing Summary\n\n_Detailed test cases are available in the Validation Report._"

    try:
        from app.ui.export_assets import asset_image_md
        from app.tiap.documentation.report_pack_generator import _appendix_md
        # Embed complexity chart in TDD's Inventory Analysis if present.
        sections["Inventory Analysis"] = (
            sections.get("Inventory Analysis", "")
            + "\n\n" + asset_image_md("Complexity_Distribution", "Complexity Distribution")
        )
        sections["Appendices"] = _appendix_md(jobs)
    except Exception as e:
        sections["Appendices"] = f"_Appendices unavailable: {e}_"

    return sections


def _lld_sections() -> Dict[str, str]:
    jobs = st.session_state.get("last_analysis_jobs", []) or []
    if not jobs:
        return {"Executive Summary": "_No repository loaded — run analysis first._"}

    sections: Dict[str, str] = {}
    repository_path = st.session_state.get("last_repo_path")
    effort = st.session_state.get("effort_estimate", {})

    try:
        from app.tiap.documentation.executive_summary_generator import ExecutiveSummaryGenerator
        sections["Executive Summary"] = ExecutiveSummaryGenerator().generate(jobs, repository_path, effort)
    except Exception as e:
        sections["Executive Summary"] = f"_Executive Summary unavailable: {e}_"

    try:
        rows = []
        for j in jobs:
            comps = j.get("job_data", {}).get("components", []) or []
            for c in comps:
                rows.append({
                    "Job": j.get("job_data", {}).get("job_name", ""),
                    "Component": c.get("name", c.get("component_name", "")),
                    "Type": c.get("type", c.get("component_type", "")),
                    "Description": str(c.get("description", ""))[:80],
                })
        sections["Component Inventory"] = (
            "# Component Inventory\n\n"
            + (_md_table(rows, ["Job", "Component", "Type", "Description"]) if rows else "_No components found._")
        )
    except Exception as e:
        sections["Component Inventory"] = f"_Component Inventory unavailable: {e}_"

    try:
        from app.tiap.documentation.functional_doc_generator import FunctionalDocGenerator
        sections["Job Specifications"] = FunctionalDocGenerator().generate(jobs)
    except Exception as e:
        sections["Job Specifications"] = f"_Job Specifications unavailable: {e}_"

    # Reuse TDD column mapping & lineage for LLD.
    tdd = _tdd_sections()
    sections["Column Mapping"] = tdd.get("Column Mapping", "")
    sections["Data Lineage"]    = tdd.get("Data Lineage", "")
    try:
        rows = []
        for j in jobs:
            for s in j.get("job_data", {}).get("schemas", []) or []:
                rows.append({
                    "Job": j.get("job_data", {}).get("job_name", ""),
                    "Schema": s.get("name", ""),
                    "Field Count": len(s.get("fields", []) or []),
                })
        sections["Schema Definitions"] = (
            "# Schema Definitions\n\n"
            + (_md_table(rows, ["Job", "Schema", "Field Count"]) if rows else "_No schemas detected._")
        )
    except Exception as e:
        sections["Schema Definitions"] = f"_Schema Definitions unavailable: {e}_"

    sections["Configuration Details"] = (
        "# Configuration Details\n\n"
        + _md_table(
            [
                {"Setting": "Source Platform", "Value": st.session_state.get("wizard_project_type", "Talend")},
                {"Setting": "Source Version", "Value": st.session_state.get("wizard_source_version", "Unknown")},
                {"Setting": "Target Version", "Value": st.session_state.get("wizard_target_version_val", "Talend 8")},
                {"Setting": "Total Jobs", "Value": len(jobs)},
            ],
            ["Setting", "Value"],
        )
    )

    try:
        from app.tiap.documentation.report_pack_generator import _appendix_md
        sections["Appendices"] = _appendix_md(jobs)
    except Exception as e:
        sections["Appendices"] = f"_Appendices unavailable: {e}_"

    return sections


def _runbook_sections() -> Dict[str, str]:
    runbook = st.session_state.get("migration_runbook")
    if not runbook:
        return {"Overview": "_Migration Runbook has not been generated yet._"}

    def _list_to_md(title: str, items: Any) -> str:
        if not items:
            return f"# {title}\n\n_No entries._"
        if isinstance(items, list):
            return f"# {title}\n\n" + "\n".join(
                f"- {x}" if not isinstance(x, dict) else f"- **{x.get('title', x.get('name', 'Step'))}** — {x.get('description', '')}"
                for x in items
            )
        return f"# {title}\n\n{json.dumps(items, indent=2, default=str)}"

    rb = runbook if isinstance(runbook, dict) else getattr(runbook, "__dict__", {})
    from app.ui.export_assets import asset_image_md
    readiness_chart = "\n\n" + asset_image_md("Pre_Migration_Readiness", "Pre-Migration Readiness")
    return {
        "Overview":                 f"# Migration Runbook Overview\n\n{rb.get('summary', '_See sections below._')}{readiness_chart}",
        "Pre-Migration Checklist":  _list_to_md("Pre-Migration Checklist", rb.get("pre_checklist") or rb.get("preflight")),
        "Cutover Plan":             _list_to_md("Cutover Plan", rb.get("cutover") or rb.get("cutover_steps")),
        "Validation Steps":         _list_to_md("Validation Steps", rb.get("validation") or rb.get("validation_steps")),
        "Rollback Plan":            _list_to_md("Rollback Plan", rb.get("rollback") or rb.get("rollback_plan")),
        "Post-Migration Tasks":     _list_to_md("Post-Migration Tasks", rb.get("post_tasks") or rb.get("postmigration")),
        "Communication Plan":       _list_to_md("Communication Plan", rb.get("communication") or rb.get("comms")),
        "Appendices":               f"# Appendices\n\n```json\n{json.dumps(rb, indent=2, default=str)[:8000]}\n```",
    }


def _arch_sections() -> Dict[str, str]:
    from app.ui.export_assets import asset_image_md
    data = st.session_state.get("architecture_autofix_intelligence")
    if not data:
        return {"Architecture Overview": "_Architecture Report has not been generated yet._"}

    d = data if isinstance(data, dict) else getattr(data, "__dict__", {})

    def _table_or_msg(rows: Any, hdr: List[str], fallback: str) -> str:
        if not rows:
            return fallback
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            return _md_table(rows, hdr)
        return f"```json\n{json.dumps(rows, indent=2, default=str)[:6000]}\n```"

    arch_diag = "\n\n" + asset_image_md("Architecture_Overview", "Architecture Overview")
    integ_diag = "\n\n" + asset_image_md("System_Integration_Map", "System Integration Map")

    return {
        "Architecture Overview":     f"# Architecture Overview\n\n{d.get('summary', d.get('overview', '_See sections below._'))}{arch_diag}",
        "Auto-Fix Recommendations":  "# Auto-Fix Recommendations\n\n" + _table_or_msg(
            d.get("auto_fix_recommendations") or d.get("recommendations"),
            ["title", "description", "priority"],
            "_No auto-fix recommendations._",
        ),
        "Cloud Readiness":           "# Cloud Readiness\n\n" + _table_or_msg(
            d.get("cloud_readiness"), ["job", "score", "status"], "_No cloud readiness details._",
        ),
        "Infrastructure":            "# Infrastructure\n\n" + _table_or_msg(
            d.get("infrastructure"), ["component", "status"], "_No infrastructure data._",
        ),
        "Integration Map":           "# Integration Map\n\n" + _table_or_msg(
            d.get("integrations"), ["source", "target", "type"], "_No integration map data._",
        ) + integ_diag,
        "Risk & Compliance":         "# Risk & Compliance\n\n" + _table_or_msg(
            d.get("risk_compliance") or d.get("risks"), ["risk", "severity", "mitigation"], "_No risk data._",
        ),
        "Appendices":                f"# Appendices\n\n```json\n{json.dumps(d, indent=2, default=str)[:8000]}\n```",
    }


def _validation_sections() -> Dict[str, str]:
    """Validation Report. Pulls from validation_framework / testing_architecture if present."""
    from app.ui.export_assets import asset_image_md
    jobs = st.session_state.get("last_analysis_jobs", []) or []
    if not jobs:
        return {"Validation Strategy": "_No repository loaded — run analysis first._"}

    sections: Dict[str, str] = {}
    sections["Validation Strategy"] = (
        "# Validation Strategy\n\n"
        "End-to-end validation strategy covers schema parity, row counts, "
        "checksum comparison, business KPI reconciliation and regression "
        "test execution against the migrated repository."
        + "\n\n" + asset_image_md("Validation_Coverage_Snapshot", "Validation Coverage Snapshot")
    )

    try:
        from app.tiap.testing.testing_architecture import TestingArchitecture
        ta = TestingArchitecture()
        plan = ta.generate(jobs) if hasattr(ta, "generate") else {}
    except Exception:
        plan = {}

    coverage = plan.get("coverage") if isinstance(plan, dict) else None
    if coverage:
        sections["Test Coverage"] = "# Test Coverage\n\n" + _md_table(
            coverage if isinstance(coverage, list) else [], ["job", "coverage", "tests"],
        )
    else:
        sections["Test Coverage"] = (
            "# Test Coverage\n\n"
            + _md_table(
                [{"Job": j.get("job_data", {}).get("job_name", ""),
                  "Components": len(j.get("job_data", {}).get("components", []) or []),
                  "Status": "Planned"} for j in jobs],
                ["Job", "Components", "Status"],
            )
        )

    sections["Validation Results"] = "# Validation Results\n\n_To be populated after validation run._"
    sections["Quality Gates"]      = (
        "# Quality Gates\n\n"
        + _md_table(
            [
                {"Gate": "Schema Parity",        "Threshold": "100%", "Status": "Pending"},
                {"Gate": "Row Count",            "Threshold": "±1%",  "Status": "Pending"},
                {"Gate": "Checksum Match",       "Threshold": "100%", "Status": "Pending"},
                {"Gate": "KPI Reconciliation",   "Threshold": "±1%",  "Status": "Pending"},
                {"Gate": "Regression Pass Rate", "Threshold": ">95%", "Status": "Pending"},
            ],
            ["Gate", "Threshold", "Status"],
        )
    )
    sections["Defects Summary"] = "# Defects Summary\n\n_No defects logged yet._"
    sections["Sign-off"] = (
        "# Sign-off\n\n"
        "| Role | Name | Date | Status |\n| --- | --- | --- | --- |\n"
        "| Migration Lead |  |  | Pending |\n"
        "| QA Lead |  |  | Pending |\n"
        "| Business Owner |  |  | Pending |\n"
    )
    return sections


def _migration_sections() -> Dict[str, str]:
    from app.ui.export_assets import asset_image_md
    sections: Dict[str, str] = {}
    mi = st.session_state.get("migration_intelligence")
    ii = st.session_state.get("impact_intelligence")
    rd = st.session_state.get("readiness_score", {})

    if mi:
        try:
            from app.ui.migration_intelligence_dashboard import export_migration_intelligence
            payload = export_migration_intelligence(mi, "json")
            text = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
        except Exception:
            text = json.dumps(mi if isinstance(mi, dict) else getattr(mi, "__dict__", {}), indent=2, default=str)
        sections["Migration Intelligence"] = (
            "# Migration Intelligence\n\n"
            + asset_image_md("Migration_Intelligence_KPIs", "Migration Intelligence KPIs")
            + f"\n\n```json\n{text[:8000]}\n```"
        )
    else:
        sections["Migration Intelligence"] = "_Migration Intelligence not generated._"

    if ii:
        try:
            from app.ui.impact_intelligence_dashboard import export_impact_intelligence
            payload = export_impact_intelligence(ii, "json")
            text = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
        except Exception:
            text = json.dumps(ii if isinstance(ii, dict) else getattr(ii, "__dict__", {}), indent=2, default=str)
        sections["Impact Intelligence"] = f"# Impact Intelligence\n\n```json\n{text[:8000]}\n```"
    else:
        sections["Impact Intelligence"] = "_Impact Intelligence not generated._"

    if rd:
        sections["Readiness Score"] = "# Readiness Score\n\n" + _md_table(
            [{"Metric": k, "Value": v} for k, v in rd.items() if not isinstance(v, (dict, list))],
            ["Metric", "Value"],
        )
    else:
        sections["Readiness Score"] = "_Readiness Score not computed._"

    sections["Wave Planning"] = (
        "# Wave Planning\n\n"
        + _md_table(
            [
                {"Wave": "Wave 1", "Scope": "Quick wins · LOW complexity", "Status": "Planned"},
                {"Wave": "Wave 2", "Scope": "MEDIUM complexity",          "Status": "Planned"},
                {"Wave": "Wave 3", "Scope": "HIGH complexity / risk",     "Status": "Planned"},
            ],
            ["Wave", "Scope", "Status"],
        )
        + "\n\n" + asset_image_md("Wave_Planning_Complexity", "Wave Planning Complexity")
    )
    sections["Recommendations"] = (
        "# Recommendations\n\n"
        "- Prioritise quick-win jobs in Wave 1.\n"
        "- Address auto-fix candidates before manual remediation.\n"
        "- Run preflight before each wave.\n"
        "- Capture validation evidence per wave.\n"
    )
    return sections


# Document → builder dispatch.
DOC_BUILDERS = {
    DOC_TDD:       _tdd_sections,
    DOC_LLD:       _lld_sections,
    DOC_RUNBOOK:   _runbook_sections,
    DOC_EXEC:      _exec_sections,
    DOC_ARCH:      _arch_sections,
    DOC_VALID:     _validation_sections,
    DOC_MIGRATION: _migration_sections,
}


def build_sections(doc_type: str, only: Optional[List[str]] = None) -> Dict[str, str]:
    builder = DOC_BUILDERS.get(doc_type)
    if not builder:
        return {"Overview": f"_No builder registered for {doc_type}._"}
    sections = builder()
    if only:
        # Preserve user's selected order; tolerate name mismatches gracefully.
        out = {k: sections[k] for k in only if k in sections}
        if not out:
            out = sections   # nothing matched → fall back to all so user gets something
        return out
    return sections


# ── Format writers (delegate to existing TMA writers) ────────────────────────

def _build_manifests(doc_type: str, sections: Dict[str, str]):
    """Build a per-section manifest mapping using the asset framework.

    The same `AssetManifest` is used for every section so that asset
    references work no matter which section embeds them. (Streamlit-side
    builders embed the same asset keys across sections.)
    """
    from app.ui.export_assets import collect_for_doc, AssetManifest
    base = collect_for_doc(doc_type)
    return {name: base for name in sections.keys()}, base


def _bytes_pdf(title: str, sections: Dict[str, str], doc_type: str) -> bytes:
    from app.ui.export_writers import pdf_bytes
    manifests, _ = _build_manifests(doc_type, sections)
    return pdf_bytes(sections, manifests, title)


def _bytes_html(title: str, sections: Dict[str, str], doc_type: str) -> bytes:
    from app.ui.export_writers import html_bytes
    manifests, _ = _build_manifests(doc_type, sections)
    return html_bytes(sections, manifests, title)


def _bytes_docx(title: str, sections: Dict[str, str], doc_type: str) -> bytes:
    from app.ui.export_writers import docx_bytes
    manifests, _ = _build_manifests(doc_type, sections)
    return docx_bytes(sections, manifests, title)


def _safe_filename(text: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in str(text)).strip("_")
    return out or "Document"


# ── Public export functions ──────────────────────────────────────────────────

def export_single(doc_type: str, fmt: str, only_sections: Optional[List[str]] = None) -> Tuple[bytes, str, str]:
    """Build a single document in the requested format.

    Returns (bytes, filename, mime_type).
    """
    sections = build_sections(doc_type, only_sections)
    base = _safe_filename(doc_type)
    if fmt == FORMAT_PDF:
        return _bytes_pdf(doc_type, sections, doc_type), f"{base}.pdf", "application/pdf"
    if fmt == FORMAT_HTML:
        return _bytes_html(doc_type, sections, doc_type), f"{base}.html", "text/html"
    if fmt == FORMAT_DOCX:
        return (
            _bytes_docx(doc_type, sections, doc_type),
            f"{base}.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    raise ValueError(f"Unsupported format: {fmt}")


def export_multiple(doc_types: List[str], fmt: str) -> Tuple[bytes, str, str]:
    """Build multiple documents merged into a single file (PDF/HTML/DOCX) or
    bundled into a ZIP archive."""
    if not doc_types:
        return b"", "Empty.zip", "application/zip"

    if fmt == FORMAT_ZIP:
        return _zip_per_document(doc_types)

    # Merge sections; manifests from every doc get unioned.
    from app.ui.export_assets import AssetManifest, collect_for_doc
    merged: Dict[str, str] = {}
    merged_manifests: Dict[str, AssetManifest] = {}
    union = AssetManifest(doc_type="Combined")
    for d in doc_types:
        m = collect_for_doc(d)
        union.assets.extend(m.assets)
    for d in doc_types:
        for sec_name, sec_md in build_sections(d).items():
            label = f"{d} — {sec_name}"
            merged[label] = sec_md
            merged_manifests[label] = union

    from app.ui.export_writers import pdf_bytes, html_bytes, docx_bytes
    if fmt == FORMAT_PDF:
        return pdf_bytes(merged, merged_manifests, "Combined Documentation"), "Combined_Documentation.pdf", "application/pdf"
    if fmt == FORMAT_HTML:
        return html_bytes(merged, merged_manifests, "Combined Documentation"), "Combined_Documentation.html", "text/html"
    if fmt == FORMAT_DOCX:
        return (
            docx_bytes(merged, merged_manifests, "Combined Documentation"),
            "Combined_Documentation.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    raise ValueError(f"Unsupported format: {fmt}")


def _zip_per_document(doc_types: List[str]) -> Tuple[bytes, str, str]:
    """ZIP containing PDF + HTML + DOCX for each document, plus shared assets."""
    from app.ui.export_assets import collect_for_doc, AssetManifest
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in doc_types:
            sections = build_sections(d)
            manifest = collect_for_doc(d)
            base = _safe_filename(d)
            try:
                from app.ui.export_writers import pdf_bytes, html_bytes, docx_bytes
                ms = {n: manifest for n in sections}
                zf.writestr(f"{base}/{base}.pdf",  pdf_bytes(sections, ms, d))
                zf.writestr(f"{base}/{base}.html", html_bytes(sections, ms, d))
                zf.writestr(f"{base}/{base}.docx", docx_bytes(sections, ms, d))
                # Per-doc asset folder.
                for a in manifest.assets:
                    zf.writestr(f"{base}/Assets/{a.filename}", a.data)
            except Exception as e:
                zf.writestr(f"{base}/{base}.error.txt", f"{e}")
    buf.seek(0)
    return buf.read(), "Documents_Bundle.zip", "application/zip"


def export_complete_package() -> Tuple[bytes, str, str]:
    """Generate the complete enterprise documentation package as a ZIP.

    Layout:
        Documentation_Package/
        ├── Index.html
        ├── Assets/         (all visual artefacts)
        ├── Images/         (PNG / JPG / SVG / GIF picked up from output/)
        ├── Charts/         (KPI / complexity / readiness charts)
        ├── Diagrams/       (architecture / lineage / flow diagrams)
        ├── TDD/            (TDD.pdf · TDD.html · TDD.docx)
        ├── LLD/
        ├── Runbook/
        ├── Executive/
        ├── Architecture/
        ├── Migration/
        └── Validation/
    """
    from app.ui.export_assets import collect_for_doc, AssetManifest, replace_assets_html
    from app.ui.export_writers import pdf_bytes, html_bytes, docx_bytes

    repo_name = st.session_state.get("last_repo_name", "Repository")
    pkg_root = "Documentation_Package"
    buf = io.BytesIO()

    # Folder mapping: align with problem-statement spec.
    FOLDER_FOR = {
        DOC_TDD:       "TDD",
        DOC_LLD:       "LLD",
        DOC_RUNBOOK:   "Runbook",
        DOC_EXEC:      "Executive",
        DOC_ARCH:      "Architecture",
        DOC_VALID:     "Validation",
        DOC_MIGRATION: "Migration",
    }

    # Collect every asset across every document so the global Assets/Images/
    # Charts/Diagrams folders contain the union (deduped on key).
    union_assets: Dict[str, Any] = {}
    per_doc_manifests: Dict[str, AssetManifest] = {}

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        index_links: List[Tuple[str, str]] = []

        for d in ALL_DOCUMENTS:
            sections = build_sections(d)
            manifest = collect_for_doc(d)
            per_doc_manifests[d] = manifest
            for a in manifest.assets:
                union_assets[a.key] = a

            folder = f"{pkg_root}/{FOLDER_FOR[d]}"
            base = _safe_filename(d)
            ms = {n: manifest for n in sections}
            try:
                zf.writestr(f"{folder}/{base}.pdf",  pdf_bytes(sections, ms, d))
                index_links.append((f"{d} (PDF)",  f"{FOLDER_FOR[d]}/{base}.pdf"))
            except Exception as e:
                zf.writestr(f"{folder}/{base}.pdf.error.txt", f"{e}")
            try:
                zf.writestr(f"{folder}/{base}.html", html_bytes(sections, ms, d))
                index_links.append((f"{d} (HTML)", f"{FOLDER_FOR[d]}/{base}.html"))
            except Exception as e:
                zf.writestr(f"{folder}/{base}.html.error.txt", f"{e}")
            try:
                zf.writestr(f"{folder}/{base}.docx", docx_bytes(sections, ms, d))
                index_links.append((f"{d} (DOCX)", f"{FOLDER_FOR[d]}/{base}.docx"))
            except Exception as e:
                zf.writestr(f"{folder}/{base}.docx.error.txt", f"{e}")

        # Shared asset folders — deduped union.
        zf.writestr(f"{pkg_root}/Assets/.keep", "")
        zf.writestr(f"{pkg_root}/Images/.keep", "")
        zf.writestr(f"{pkg_root}/Charts/.keep", "")
        zf.writestr(f"{pkg_root}/Diagrams/.keep", "")
        for a in union_assets.values():
            zf.writestr(f"{pkg_root}/Assets/{a.filename}", a.data)
            sub = {"image": "Images", "chart": "Charts",
                   "diagram": "Diagrams", "lineage": "Diagrams"}.get(a.kind, "Assets")
            zf.writestr(f"{pkg_root}/{sub}/{a.filename}", a.data)

        # Index.html — group links by document.
        grouped: Dict[str, List[Tuple[str, str]]] = {}
        for label, href in index_links:
            doc = label.split(" (")[0]
            grouped.setdefault(doc, []).append((label, href))

        groups_html = []
        for doc, links in grouped.items():
            items = "".join(
                f'<li><a href="{href}">{label}</a></li>' for label, href in links
            )
            groups_html.append(
                f'<div class="card"><h3>{doc}</h3><ul>{items}</ul></div>'
            )
        cards_html = "".join(groups_html)

        # Build a mini gallery of the most relevant visuals in Index.html.
        gallery_html = ""
        gallery_items = list(union_assets.values())[:12]
        if gallery_items:
            tiles = "".join(
                f'<figure><img src="Assets/{a.filename}" alt="{a.caption}"/>'
                f'<figcaption>{a.caption}</figcaption></figure>'
                for a in gallery_items
            )
            gallery_html = f'<section><h2>Visuals</h2><div class="gallery">{tiles}</div></section>'

        idx_html = f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<title>{repo_name} — Documentation Package</title>
<style>
  body {{ font-family:'Inter',Arial,sans-serif; margin:40px; color:#1a1a1a; }}
  h1 {{ color:#1a3c6e; border-bottom:2px solid #1a3c6e; padding-bottom:6px; }}
  h2 {{ color:#1d4ed8; margin-top:32px; }}
  h3 {{ color:#1a3c6e; margin:0 0 8px; }}
  .meta {{ color:#6b7280; font-size:12px; margin-bottom:24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; }}
  .card {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px;
            padding:16px 18px; }}
  .card ul {{ margin:0; padding-left:18px; line-height:1.9; }}
  .card a {{ color:#1d4ed8; text-decoration:none; }}
  .gallery {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
              gap:14px; margin-top:14px; }}
  figure {{ margin:0; background:#fff; border:1px solid #e2e8f0; border-radius:10px;
            padding:8px; text-align:center; }}
  figure img {{ max-width:100%; height:auto; border-radius:6px; }}
  figcaption {{ font-size:11px; color:#475569; margin-top:6px; font-style:italic; }}
</style></head><body>
<h1>{repo_name} — Documentation Package</h1>
<div class="meta">Generated by Talend Migration Accelerator on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
<section><h2>Documents</h2><div class="grid">{cards_html}</div></section>
{gallery_html}
</body></html>"""
        zf.writestr(f"{pkg_root}/Index.html", idx_html)

    buf.seek(0)
    return buf.read(), "Documentation_Package.zip", "application/zip"


# ── UI rendering ─────────────────────────────────────────────────────────────

def _document_availability() -> Dict[str, bool]:
    jobs = st.session_state.get("last_analysis_jobs", []) or []
    return {
        DOC_TDD:       bool(jobs),
        DOC_LLD:       bool(jobs),
        DOC_RUNBOOK:   bool(st.session_state.get("migration_runbook")),
        DOC_EXEC:      bool(jobs),
        DOC_ARCH:      bool(st.session_state.get("architecture_autofix_intelligence")),
        DOC_VALID:     bool(jobs),
        DOC_MIGRATION: bool(st.session_state.get("migration_intelligence") or st.session_state.get("impact_intelligence") or jobs),
    }


def _estimated_pages(doc_types: List[str], sections_per_doc: Optional[Dict[str, List[str]]] = None) -> int:
    total = 0
    for d in doc_types:
        secs = (sections_per_doc or {}).get(d) or DOC_SECTIONS.get(d, [])
        total += max(1, len(secs))
    # Each section conservatively ~1.5 pages.
    return int(total * 1.5)


def _estimated_kb(doc_types: List[str], fmt: str) -> int:
    per_format = {
        FORMAT_PDF: 90,
        FORMAT_HTML: 50,
        FORMAT_DOCX: 70,
        FORMAT_ZIP: 240,
    }
    return max(20, len(doc_types) * per_format.get(fmt, 80))


def _compute_visual_preview(doc_types: List[str]) -> Dict[str, int]:
    """Snapshot of how many visuals the selected documents will embed."""
    from app.ui.export_assets import collect_for_doc
    out = {"images": 0, "charts": 0, "diagrams": 0, "lineage": 0, "bytes": 0}
    seen = set()
    for d in doc_types:
        m = collect_for_doc(d)
        for a in m.assets:
            if a.key in seen:
                continue
            seen.add(a.key)
            if a.kind == "image":
                out["images"] += 1
            elif a.kind == "chart":
                out["charts"] += 1
            elif a.kind == "diagram":
                out["diagrams"] += 1
            elif a.kind == "lineage":
                out["lineage"] += 1
            out["bytes"] += len(a.data)
    return out


def render_export_center() -> None:
    """Public entry point: render the Export Center UI inside Documentation Hub."""
    _init_state()
    _inject_export_center_css()

    st.markdown(
        '<div class="ec-hero">'
        '<div class="ec-hero-icon">⬇</div>'
        '<div>'
        '<div class="ec-hero-title">Export Center</div>'
        '<div class="ec-hero-sub">PDF · HTML · DOCX · ZIP — every visual the UI shows is embedded into the export.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    availability = _document_availability()
    if not any(availability.values()):
        empty_state_card(
            "No documents available",
            "Upload and analyse a Talend repository (and run the related dashboards) to enable exports.",
            "warning",
        )
        return

    # ── 1. Export Mode (segmented control) ─────────────────────────────────
    section_header("1. Export Mode")
    # We can't have one tab "selected" via st.tabs alone; use a segmented_control underneath
    # for modes (kept compatible across Streamlit versions).
    try:
        seg = st.segmented_control(
            "Mode", EC_MODES,
            default=st.session_state[_SS_MODE],
            key="ec2_mode_seg",
            label_visibility="collapsed",
        )
        if seg:
            st.session_state[_SS_MODE] = seg
    except Exception:
        # Fallback to radio for older Streamlit versions.
        seg = st.radio(
            "Mode", EC_MODES,
            index=EC_MODES.index(st.session_state[_SS_MODE]),
            horizontal=True, key="ec2_mode_radio", label_visibility="collapsed",
        )
        st.session_state[_SS_MODE] = seg
    mode = st.session_state[_SS_MODE]

    # ── 2. Document selection ─────────────────────────────────────────────
    section_header("2. Documents")
    if mode == EC_MODE_CURRENT:
        active = [d for d in ALL_DOCUMENTS if availability.get(d)]
        if not active:
            st.info("No documents available yet.")
            return
        cur = st.selectbox(
            "Current Document",
            active,
            index=active.index(st.session_state[_SS_CURRENT]) if st.session_state[_SS_CURRENT] in active else 0,
            key="ec2_current_radio",
        )
        st.session_state[_SS_CURRENT] = cur
        selected_docs = [cur]
    elif mode == EC_MODE_SECTIONS:
        active = [d for d in ALL_DOCUMENTS if availability.get(d)]
        cur = st.selectbox(
            "Document",
            active,
            index=active.index(st.session_state[_SS_CURRENT]) if st.session_state[_SS_CURRENT] in active else 0,
            key="ec2_sec_doc",
        )
        st.session_state[_SS_CURRENT] = cur
        selected_docs = [cur]
    elif mode == EC_MODE_MULTI:
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Select All", key="ec2_select_all", use_container_width=True):
                st.session_state[_SS_DOCS] = [d for d in ALL_DOCUMENTS if availability.get(d)]
        with c2:
            if st.button("Deselect All", key="ec2_deselect_all", use_container_width=True):
                st.session_state[_SS_DOCS] = []
        chosen: List[str] = []
        cols = st.columns(3)
        for i, d in enumerate(ALL_DOCUMENTS):
            with cols[i % 3]:
                disabled = not availability.get(d, False)
                checked = st.checkbox(
                    f"{d}{'  (unavailable)' if disabled else ''}",
                    value=d in st.session_state[_SS_DOCS] and not disabled,
                    disabled=disabled,
                    key=f"ec2_doc_chk_{d}",
                )
                if checked and not disabled:
                    chosen.append(d)
        st.session_state[_SS_DOCS] = chosen
        selected_docs = chosen
    else:
        # Package — all available documents are bundled.
        selected_docs = [d for d in ALL_DOCUMENTS if availability.get(d)]
        st.info(f"All available documents will be packaged: {', '.join(selected_docs)}")

    # ── 3. Section selection ──────────────────────────────────────────────
    section_header("3. Sections")
    sections_per_doc: Dict[str, List[str]] = st.session_state[_SS_SECTIONS]
    if mode == EC_MODE_SECTIONS and selected_docs:
        d = selected_docs[0]
        all_sections = DOC_SECTIONS.get(d, [])
        c1, c2, _ = st.columns([1, 1, 4])
        with c1:
            if st.button("Select All Sections", key=f"ec2_sa_{d}", use_container_width=True):
                sections_per_doc[d] = list(all_sections)
        with c2:
            if st.button("Deselect All Sections", key=f"ec2_da_{d}", use_container_width=True):
                sections_per_doc[d] = []
        chosen_sections: List[str] = []
        cols = st.columns(3)
        for i, sec in enumerate(all_sections):
            with cols[i % 3]:
                checked = st.checkbox(
                    sec,
                    value=sec in (sections_per_doc.get(d, all_sections) or []),
                    key=f"ec2_sec_chk_{d}_{sec}",
                )
                if checked:
                    chosen_sections.append(sec)
        sections_per_doc[d] = chosen_sections
        st.session_state[_SS_SECTIONS] = sections_per_doc
    else:
        st.caption("Section filtering is only available in **Export Selected Sections**. "
                   "Other modes export all available sections per document.")

    # ── 4. Output Format ──────────────────────────────────────────────────
    section_header("4. Format")
    formats = MODE_FORMATS[mode]
    if st.session_state[_SS_FORMAT] not in formats:
        st.session_state[_SS_FORMAT] = formats[0]
    try:
        fmt = st.segmented_control(
            "Format", formats,
            default=st.session_state[_SS_FORMAT],
            key="ec2_fmt_seg", label_visibility="collapsed",
        ) or st.session_state[_SS_FORMAT]
    except Exception:
        fmt = st.radio(
            "Format", formats,
            index=formats.index(st.session_state[_SS_FORMAT]),
            horizontal=True, key="ec2_fmt_radio", label_visibility="collapsed",
        )
    st.session_state[_SS_FORMAT] = fmt

    # ── 5. Preview (visuals + summary cards) ──────────────────────────────
    section_header("5. Preview")
    docs_count = len(selected_docs)
    if mode == EC_MODE_SECTIONS and selected_docs:
        total_secs = len(sections_per_doc.get(selected_docs[0], []))
    else:
        total_secs = sum(len(DOC_SECTIONS.get(d, [])) for d in selected_docs)
    pages = _estimated_pages(selected_docs, sections_per_doc if mode == EC_MODE_SECTIONS else None)
    size_kb = _estimated_kb(selected_docs, fmt)
    visuals = _compute_visual_preview(selected_docs) if selected_docs else {
        "images": 0, "charts": 0, "diagrams": 0, "lineage": 0, "bytes": 0
    }

    s1, s2, s3, s4 = st.columns(4)
    with s1: _ec_summary_card("Documents",      str(docs_count), "selected", "#1d4ed8")
    with s2: _ec_summary_card("Sections",       str(total_secs), "included", "#0f766e")
    with s3: _ec_summary_card("Estimated Pages", str(pages),     "approx.",  "#6d28d9")
    with s4: _ec_summary_card("Estimated Size", f"~{size_kb} KB", "package", "#b45309")

    v1, v2, v3, v4, v5 = st.columns(5)
    with v1: _ec_summary_card("Images",   str(visuals["images"]),   "PNG/JPG/SVG", "#0ea5e9")
    with v2: _ec_summary_card("Charts",   str(visuals["charts"]),   "Plotly/MPL",  "#22c55e")
    with v3: _ec_summary_card("Diagrams", str(visuals["diagrams"]), "Mermaid/DOT", "#a855f7")
    with v4: _ec_summary_card("Lineage",  str(visuals["lineage"]),  "NetworkX",    "#f59e0b")
    with v5: _ec_summary_card("Assets Size", f"{visuals['bytes'] // 1024} KB", "embedded", "#475569")

    # ── 6. Generate Export ────────────────────────────────────────────────
    section_header("6. Generate")
    can_run = bool(selected_docs) and (mode != EC_MODE_SECTIONS or total_secs > 0)
    label = {
        EC_MODE_CURRENT:  "Generate Document",
        EC_MODE_SECTIONS: "Generate Selected Sections",
        EC_MODE_MULTI:    "Generate Documents",
        EC_MODE_PACKAGE:  "Generate Complete Package",
    }[mode]

    if st.button(label, type="primary", disabled=not can_run, key="ec2_run_btn", use_container_width=True):
        try:
            with st.spinner("Generating export — rendering visuals…"):
                if mode == EC_MODE_CURRENT:
                    data, fname, mime = export_single(selected_docs[0], fmt)
                elif mode == EC_MODE_SECTIONS:
                    data, fname, mime = export_single(
                        selected_docs[0], fmt, sections_per_doc.get(selected_docs[0]),
                    )
                elif mode == EC_MODE_MULTI:
                    data, fname, mime = export_multiple(selected_docs, fmt)
                else:
                    data, fname, mime = export_complete_package()
            st.session_state["ec2_last_bytes"] = data
            st.session_state["ec2_last_name"]  = fname
            st.session_state["ec2_last_mime"]  = mime
            st.success(f"Generated **{fname}** ({len(data) // 1024} KB · {visuals['images']} img · {visuals['charts']} chart · {visuals['diagrams']} diagram).")
        except Exception as e:
            st.error(f"Export failed: {e}")

    if st.session_state.get("ec2_last_bytes"):
        st.download_button(
            f"Download {st.session_state.get('ec2_last_name', 'Export')}",
            data=st.session_state["ec2_last_bytes"],
            file_name=st.session_state.get("ec2_last_name", "Export"),
            mime=st.session_state.get("ec2_last_mime", "application/octet-stream"),
            use_container_width=True,
            key="ec2_dl_last",
        )


def _ec_summary_card(label: str, value: str, caption: str, color: str = "#1d4ed8") -> None:
    st.markdown(
        f'<div class="ec-card" style="border-left-color:{color};">'
        f'<div class="ec-card-label">{label}</div>'
        f'<div class="ec-card-value" style="color:{color};">{value}</div>'
        f'<div class="ec-card-caption">{caption}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _inject_export_center_css() -> None:
    st.markdown(
        """
<style>
.ec-hero {
    display:flex; align-items:center; gap:18px;
    background:linear-gradient(120deg,#0f172a,#1d4ed8);
    color:#fff; border-radius:14px; padding:18px 22px; margin:8px 0 18px;
    box-shadow:0 1px 2px rgba(15,23,42,.04);
}
.ec-hero-icon {
    width:46px; height:46px; border-radius:12px;
    background:rgba(255,255,255,.16); display:flex; align-items:center;
    justify-content:center; font-size:22px; font-weight:700;
}
.ec-hero-title { font-size:18px; font-weight:800; letter-spacing:.01em; }
.ec-hero-sub { font-size:12px; opacity:.85; margin-top:2px; }

.ec-card {
    background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid #1d4ed8;
    border-radius:10px; padding:12px 14px; margin:4px 0;
}
.ec-card-label { font-size:11px; color:#64748b; font-weight:700;
                  text-transform:uppercase; letter-spacing:.06em; }
.ec-card-value { font-size:22px; font-weight:800; line-height:1.1;
                  margin-top:4px; }
.ec-card-caption { font-size:11px; color:#64748b; margin-top:2px; }
</style>
        """,
        unsafe_allow_html=True,
    )
