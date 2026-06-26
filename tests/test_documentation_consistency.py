"""
F5.7 — Documentation consistency regression tests.
Guards the canonical engine introduced in F5.2–F5.6:
  - tdd_sections SectionProvider registry stays complete/consistent
  - ai_doc_generator routes every public doc type through one registry
  - export_utils shared renderers (markdown_fragment_to_html, resolve_source_version)
    produce identical output regardless of caller
  - no module reintroduces a local duplicate of a canonical renderer
"""
import re

from app.tiap.documentation import tdd_sections
from app.generators import ai_doc_generator
from app.tiap.documentation import export_utils
from app.reports import excel_export, json_export


def _job(job_name="TestJob", components=None, column_mappings=None):
    return {
        "job_name": job_name,
        "components": [{"component_type": c} for c in (components or ["tFileInputDelimited", "tMap", "tFileOutputDelimited"])],
        "connections": [],
        "column_mappings": column_mappings or [],
        "contexts": {},
    }


# ── tdd_sections canonical registry (F5.3) ────────────────────────────────────

def test_section_registry_matches_individual_generators():
    job = _job()
    registry_result = tdd_sections.generate_all_sections(job)
    expected = {
        "validation": tdd_sections.generate_validation_section(job),
        "error_handling": tdd_sections.generate_error_handling_section(job),
        "audit_monitoring": tdd_sections.generate_audit_monitoring_section(job),
        "performance": tdd_sections.generate_performance_section(job),
        "security": tdd_sections.generate_security_section(job),
        "dependency": tdd_sections.generate_dependency_section(job),
        "transformation": tdd_sections.generate_transformation_section(job),
        "job_flow": tdd_sections.generate_job_flow_section(job),
        "column_lineage": tdd_sections.generate_column_lineage_section(job),
    }
    assert registry_result == expected


def test_section_registry_keys_are_stable():
    assert set(tdd_sections.generate_all_sections(_job()).keys()) == {
        "validation", "error_handling", "audit_monitoring", "performance",
        "security", "dependency", "transformation", "job_flow", "column_lineage",
    }


def test_each_section_provider_returns_findings_list():
    sections = tdd_sections.generate_all_sections(_job())
    for key, result in sections.items():
        assert "findings" in result, f"section '{key}' missing 'findings' key"
        assert isinstance(result["findings"], list)


# ── ai_doc_generator canonical registry (F5.4) ────────────────────────────────

def test_doc_registry_has_all_four_doc_types():
    assert set(ai_doc_generator._DOC_REGISTRY.keys()) == {"technical", "functional", "kt", "migration"}


def test_public_wrappers_delegate_to_generate_doc(monkeypatch):
    calls = []

    def fake_generate_doc(doc_type, job_data, use_ai=True):
        calls.append((doc_type, use_ai))
        return f"stub-{doc_type}"

    monkeypatch.setattr(ai_doc_generator, "generate_doc", fake_generate_doc)
    assert ai_doc_generator.generate_tech_doc(_job(), use_ai=False) == "stub-technical"
    assert ai_doc_generator.generate_functional_doc(_job()) == "stub-functional"
    assert ai_doc_generator.generate_kt_doc(_job()) == "stub-kt"
    assert ai_doc_generator.generate_migration_doc(_job()) == "stub-migration"
    assert calls == [
        ("technical", False), ("functional", True), ("kt", True), ("migration", True),
    ]


def test_generate_doc_rejects_unknown_type():
    try:
        ai_doc_generator.generate_doc("nonexistent", _job(), use_ai=False)
        assert False, "expected KeyError for unregistered doc type"
    except KeyError:
        pass


# ── export_utils shared renderers (F5.5/F5.6) ─────────────────────────────────

def test_markdown_fragment_to_html_renders_table():
    md = "# Title\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- bullet one\n"
    out = export_utils.markdown_fragment_to_html(md)
    assert "<table" in out
    assert "<th>A</th>" in out
    assert "<li>bullet one</li>" in out
    assert "<!doctype html" not in out.lower()  # fragment, not full document


def test_markdown_fragment_to_html_escapes_html():
    out = export_utils.markdown_fragment_to_html("- <script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_resolve_source_version_falls_back_to_job_data():
    jobs = [{"job_data": {"source_version": "Talend 6"}}]
    assert export_utils.resolve_source_version(jobs, repository_path=None) == "Talend 6"


def test_resolve_source_version_defaults_unknown():
    assert export_utils.resolve_source_version([], repository_path=None) == "UNKNOWN"


def test_excel_and_json_export_share_one_resolver():
    """F5.5: both modules must delegate to the same canonical implementation,
    not maintain independent copies."""
    assert excel_export._resolve_source_version is export_utils.resolve_source_version
    assert json_export._resolve_source_version is export_utils.resolve_source_version


# ── Anti-regression: no re-introduced local duplicate renderer ───────────────

def test_report_pack_generator_has_no_local_markdown_to_html():
    import app.tiap.documentation.report_pack_generator as rpg
    assert not hasattr(rpg, "_markdown_to_html"), (
        "local _markdown_to_html duplicate reappeared — use "
        "export_utils.markdown_fragment_to_html instead (F5.5)"
    )


def test_report_pack_generator_imports_canonical_fragment_renderer():
    import app.tiap.documentation.report_pack_generator as rpg
    assert rpg.markdown_fragment_to_html is export_utils.markdown_fragment_to_html
