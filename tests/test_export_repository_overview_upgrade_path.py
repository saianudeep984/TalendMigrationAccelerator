"""
Validation tests: RepositoryOverview and UpgradePath data in HTML/PDF exports.
Covers:
  - Section functions (_repository_overview_section, _upgrade_path_section)
  - HTML export includes both sections with correct content
  - PDF export is generated without errors and has non-trivial file size
  - build_report_pack_sections keys include both new sections
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.analyzers.models import RepositoryOverview
from app.tiap.documentation.report_pack_generator import (
    _repository_overview_section,
    _upgrade_path_section,
    build_report_pack_sections,
    write_complete_assessment_html,
    write_complete_assessment_pdf,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_job(name: str, source_version: str = "Talend 6", components=None):
    return {
        "job_data": {
            "job_name": name,
            "source_version": source_version,
            "components": [{"component_type": c} for c in (components or ["tMap"])],
        }
    }


SAMPLE_JOBS = [
    _make_job("Job_Alpha", "Talend 6", ["tMap", "tFTPGet", "tJavaFlex"]),
    _make_job("Job_Beta",  "Talend 7", ["tMap", "tLogRow"]),
]


def _minimal_overview() -> RepositoryOverview:
    return RepositoryOverview(
        total_jobs=2,
        total_components=5,
        total_routines=1,
        total_joblets=0,
        complexity_score=42,
        migration_readiness_score=65,
        cloud_readiness_score=70,
        testing_readiness_score=50,
        repository_type="Standard",
        source_version="Talend 6",
        enterprise_features=["tMDM", "tESB"],
        target_versions=["Talend 8"],
        migration_risk="MEDIUM",
        upgrade_path_summary="3 component change(s) required to upgrade from Talend 6 to Talend 8.",
    )


# ── _repository_overview_section ──────────────────────────────────────────────

class TestRepositoryOverviewSection:

    def test_returns_string(self):
        md = _repository_overview_section(_minimal_overview())
        assert isinstance(md, str) and len(md) > 0

    def test_contains_heading(self):
        md = _repository_overview_section(_minimal_overview())
        assert "# Repository Overview" in md

    def test_contains_kpi_fields(self):
        md = _repository_overview_section(_minimal_overview())
        assert "Total Jobs: 2" in md
        assert "Total Components: 5" in md
        assert "Complexity Score: 42%" in md
        assert "Migration Readiness Score: 65%" in md
        assert "Cloud Readiness Score: 70%" in md

    def test_contains_version_info(self):
        md = _repository_overview_section(_minimal_overview())
        assert "Talend 6" in md
        assert "Repository Type: Standard" in md

    def test_contains_upgrade_path_summary(self):
        md = _repository_overview_section(_minimal_overview())
        assert "Upgrade Path Summary" in md
        assert "component change" in md.lower()

    def test_contains_enterprise_features(self):
        md = _repository_overview_section(_minimal_overview())
        assert "Enterprise Features Detected" in md
        assert "tMDM" in md
        assert "tESB" in md

    def test_contains_target_versions(self):
        md = _repository_overview_section(_minimal_overview())
        assert "Talend 8" in md

    def test_no_enterprise_features_omits_section(self):
        ov = _minimal_overview()
        ov.enterprise_features = []
        md = _repository_overview_section(ov)
        assert "Enterprise Features Detected" not in md

    def test_migration_risk_present(self):
        md = _repository_overview_section(_minimal_overview())
        assert "Migration Risk: MEDIUM" in md


# ── _upgrade_path_section ─────────────────────────────────────────────────────

class TestUpgradePathSection:

    def test_returns_string(self):
        result = _upgrade_path_section(SAMPLE_JOBS)
        assert isinstance(result, str) and len(result) > 0

    def test_heading_present(self):
        result = _upgrade_path_section(SAMPLE_JOBS)
        assert "# Upgrade Path" in result

    def test_unknown_source_returns_graceful_message(self):
        result = _upgrade_path_section([])
        assert "could not be detected" in result.lower() or "unavailable" in result.lower() or "unknown" in result.lower()

    def test_per_job_summary_table_headers(self):
        result = _upgrade_path_section(SAMPLE_JOBS)
        assert "Job Name" in result
        assert "Status" in result
        assert "Findings" in result
        assert "Blockers" in result

    def test_job_names_appear_in_output(self):
        result = _upgrade_path_section(SAMPLE_JOBS)
        assert "Job_Alpha" in result
        assert "Job_Beta" in result

    def test_contains_totals(self):
        result = _upgrade_path_section(SAMPLE_JOBS)
        assert "Total Component Findings" in result
        assert "Total Blockers" in result


# ── build_report_pack_sections keys ───────────────────────────────────────────

class TestBuildReportPackSectionsKeys:

    def test_repository_overview_key_present(self):
        sections = build_report_pack_sections(SAMPLE_JOBS)
        assert "Repository Overview" in sections

    def test_upgrade_path_key_present(self):
        sections = build_report_pack_sections(SAMPLE_JOBS)
        assert "Upgrade Path" in sections

    def test_repository_overview_content_nonempty(self):
        sections = build_report_pack_sections(SAMPLE_JOBS)
        assert len(sections["Repository Overview"]) > 50

    def test_upgrade_path_content_nonempty(self):
        sections = build_report_pack_sections(SAMPLE_JOBS)
        assert len(sections["Upgrade Path"]) > 50

    def test_repository_overview_contains_total_jobs(self):
        sections = build_report_pack_sections(SAMPLE_JOBS)
        assert "Total Jobs" in sections["Repository Overview"]

    def test_upgrade_path_contains_heading(self):
        sections = build_report_pack_sections(SAMPLE_JOBS)
        assert "Upgrade Path" in sections["Upgrade Path"]

    def test_existing_sections_still_present(self):
        sections = build_report_pack_sections(SAMPLE_JOBS)
        for key in ("Executive Summary", "Readiness Scores", "Migration Assessment"):
            assert key in sections, f"Missing section: {key}"


# ── HTML export ───────────────────────────────────────────────────────────────

class TestHTMLExport:

    def _build_html(self) -> str:
        sections = build_report_pack_sections(SAMPLE_JOBS)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            path = f.name
        try:
            write_complete_assessment_html(path, sections)
            with open(path, encoding="utf-8") as f:
                return f.read()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_html_is_valid_document(self):
        html = self._build_html()
        assert html.startswith("<!DOCTYPE html")
        assert "</html>" in html

    def test_html_contains_repository_overview_heading(self):
        html = self._build_html()
        assert "Repository Overview" in html

    def test_html_contains_upgrade_path_heading(self):
        html = self._build_html()
        assert "Upgrade Path" in html

    def test_html_contains_total_jobs(self):
        html = self._build_html()
        assert "Total Jobs" in html

    def test_html_contains_job_names(self):
        html = self._build_html()
        assert "Job_Alpha" in html
        assert "Job_Beta" in html

    def test_html_table_tags_present(self):
        """RepositoryOverview and UpgradePath sections include markdown tables
        that must render as real <table> elements in the HTML export."""
        html = self._build_html()
        assert "<table" in html

    def test_html_table_header_row(self):
        html = self._build_html()
        assert "<th>" in html or "<th " in html

    def test_html_toc_includes_repository_overview(self):
        html = self._build_html()
        assert "Repository Overview" in html

    def test_html_toc_includes_upgrade_path(self):
        html = self._build_html()
        assert "Upgrade Path" in html

    def test_html_kpi_fields_rendered(self):
        html = self._build_html()
        assert "Migration Readiness" in html or "Migration Risk" in html


# ── PDF export ────────────────────────────────────────────────────────────────

class TestPDFExport:

    def _build_pdf(self) -> str:
        sections = build_report_pack_sections(SAMPLE_JOBS)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        write_complete_assessment_pdf(path, sections)
        return path

    def test_pdf_file_created(self):
        path = self._build_pdf()
        try:
            assert os.path.exists(path)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_pdf_file_nontrivial_size(self):
        path = self._build_pdf()
        try:
            size = os.path.getsize(path)
            assert size > 1024, f"PDF too small: {size} bytes"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_pdf_starts_with_pdf_header(self):
        path = self._build_pdf()
        try:
            with open(path, "rb") as f:
                header = f.read(8)
            assert header.startswith(b"%PDF-"), f"Not a PDF: {header!r}"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_pdf_contains_repository_overview_text(self):
        """Verify 'Repository Overview' appears in the PDF (extracted text)."""
        path = self._build_pdf()
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            text = "".join(page.extract_text() or "" for page in reader.pages)
            assert "Repository Overview" in text, "Repository Overview not found in PDF text"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_pdf_contains_upgrade_path_text(self):
        """Verify 'Upgrade Path' appears in the PDF (extracted text)."""
        path = self._build_pdf()
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            text = "".join(page.extract_text() or "" for page in reader.pages)
            assert "Upgrade Path" in text, "Upgrade Path not found in PDF text"
        finally:
            if os.path.exists(path):
                os.unlink(path)
