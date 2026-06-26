import ast
import os
import zipfile
from io import BytesIO


def _job360_src_path():
    return os.path.join(os.path.dirname(__file__), "..", "app", "ui", "job_analysis_page.py")


def _job360_src():
    with open(_job360_src_path(), encoding="utf-8-sig") as f:
        return f.read()


def _job360_module_value(name):
    tree = ast.parse(_job360_src())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found")


def test_job360_section_category_moves():
    categories = _job360_module_value("JOB360_SECTION_CATEGORIES")

    expected = {
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

    assert categories == expected


def test_job360_category_navigation_labels_are_preserved():
    assert _job360_module_value("JOB360_CATEGORY_LABELS") == [
        "Overview",
        "Executive & Migration",
        "Architecture",
        "Mapping & Lineage",
        "Technical Analysis",
        "Documentation",
        "Export Center",
    ]


def test_job360_tab_labels_expose_moved_sections():
    src = _job360_src()

    assert '["Dashboard", "Summary", "Functional", "Executive Summary", "AI Summary"]' in src
    assert '["Executive Flow", "Migration", "AI Copilot", "Migration Assessment", "Validation"]' in src
    assert '["Flowcharts", "Data Flow", "Dependencies", "Job Architecture", "Source Architecture", "Target Architecture", "Transformation Architecture", "Job Flow Architecture"]' in src
    assert '["Column Mapping", "Source-To-Target Mapping", "Column Lineage", "Lineage"]' in src
    assert '["SQL", "Java Logic", "Error Handling", "Audit", "Performance", "Security"]' in src
    assert '["Documentation Summary", "TDD", "Docs Hub", "Testing"]' in src
    assert '["Export Reports"]' in src


def test_overview_dashboard_displays_job360_metadata_contract():
    src = _job360_src()
    dashboard_block = src.split("with _ov_dash:", 1)[1].split("with _ov_summary:", 1)[0]

    for label in (
        "Job Name",
        "Source Count",
        "Target Count",
        "Component Count",
        "Mapping Count",
        "SQL Objects",
        "Java Objects",
        "Dependency Count",
        "Complexity Score",
        "Migration Readiness",
        "Validation Score",
        "Risk Score",
        "Estimated Effort",
        "Quick Insights",
        "Sources Detected",
        "Targets Detected",
        "Mappings Extracted",
        "Unsupported Components",
        "Complex Java Logic",
        "Migration Risks",
        "AI Summary",
        "Job Purpose",
        "Source Systems",
        "Target Systems",
        "Key Transformations",
        "Risks",
        "Recommendations",
    ):
        assert label in dashboard_block

    for duplicate_scan in (
        "build_repository_inventory",
        "scan_repository",
        "parse_repository",
        "analyze_repository",
    ):
        assert duplicate_scan not in dashboard_block


def test_documentation_category_is_clean():
    src = _job360_src()
    docs_block = src.split('if _cat_sel == "Documentation":', 1)[1].split('if _cat_sel == "Export Center":', 1)[0]

    assert '["Documentation Summary", "TDD", "Docs Hub", "Testing"]' in docs_block
    assert "_render_documentation_summary(job, jd, _inv, _all_recs, _sql_ops, job_name)" in docs_block
    for moved in (
        "Executive Flow",
        "Migration Assessment",
        "Flowcharts",
        "Job Architecture",
        "Source-To-Target Mapping",
        "Java Logic",
        "Error Handling",
        "Security",
    ):
        assert moved not in docs_block


def test_no_metadata_category_or_duplicate_top_level_sections():
    labels = _job360_module_value("JOB360_CATEGORY_LABELS")
    assert "Metadata" not in labels
    assert len(labels) == len(set(labels))


def test_job360_route_is_preserved():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app", "ui", "streamlit_app.py")
    with open(app_path, encoding="utf-8") as f:
        src = f.read()

    assert 'if _sel == "job_analysis":' in src
    assert 'from app.ui.job_analysis_page import render_job_analysis_page' in src


def test_export_center_supports_phase8_formats_sections_and_cache_labels():
    src = _job360_src()

    assert 'PHASE8_EXPORT_SECTIONS = ["Overview", "Architecture", "Mapping", "Lineage", "SQL", "Java", "Documentation"]' in src
    assert '["PDF", "DOCX", "HTML", "ZIP"]' in src
    assert "Prepare Export" in src
    assert "Export HTML" not in src
    assert "_360_html_" not in src
    assert "pdf_sections" not in src
    for cache_label in ("metadata", "sql_analysis", "java_analysis", "lineage", "documentation"):
        assert cache_label in src


def test_export_center_generates_all_formats_from_cached_job360_metadata():
    from app.ui.job_analysis_page import (
        PHASE8_EXPORT_SECTIONS,
        _phase8_export_bytes,
        _phase8_export_sections,
    )

    job = {
        "job_data": {"components": [{"unique_name": "src", "component_type": "tDBInput", "purpose": "read"}]},
        "complexity": {"complexity": "LOW", "score": 12, "risk_factors": []},
        "dependencies": {"child_jobs": ["child_job"], "routines": ["RoutineA"], "contexts": ["Default"]},
    }
    inv = {"sources": [{"name": "SRC_TABLE"}], "targets": [{"name": "TGT_TABLE"}]}
    all_recs = [{
        "job_name": "DemoJob",
        "category": "Validation",
        "issue": "Check counts",
        "fix": "Run reconciliation",
        "auto_fix": False,
    }]
    sql_ops = [{"component": "src", "db_type": "oracle", "query": "select * from SRC_TABLE"}]
    cached = {
        "level": "LOW",
        "score": 12,
        "effort": 4,
        "sources": ["SRC_TABLE"],
        "targets": ["TGT_TABLE"],
        "flow_steps": [("", "Read", "SRC_TABLE")],
    }

    sections = _phase8_export_sections(job, job["job_data"], inv, all_recs, sql_ops, "DemoJob", cached)
    assert list(sections) == PHASE8_EXPORT_SECTIONS

    for fmt in ("PDF", "DOCX", "HTML", "ZIP"):
        data, filename, mime = _phase8_export_bytes(sections, PHASE8_EXPORT_SECTIONS, fmt, "DemoJob Export")
        assert len(data) > 100
        assert filename.lower().endswith(fmt.lower() if fmt != "DOCX" else "docx")
        assert mime

    zip_data, _, _ = _phase8_export_bytes(sections, PHASE8_EXPORT_SECTIONS, "ZIP", "DemoJob Export")
    with zipfile.ZipFile(BytesIO(zip_data)) as zf:
        assert sorted(zf.namelist()) == [
            "DemoJob_Export.docx",
            "DemoJob_Export.html",
            "DemoJob_Export.pdf",
            "manifest.json",
        ]
