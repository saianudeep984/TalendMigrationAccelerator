# TMA TDD Export Engine

## Overview
Per-job TDD export pipeline producing Markdown, HTML, DOCX, and PDF, with filenames
following `<Job_Name>_TDD.<ext>` (job name sanitized to `[A-Za-z0-9_]`).

## Content Assembly
`build_tdd_markdown(job_data)` assembles one markdown document by calling directly
into the section generators built in Phases 14–17 — no logic is duplicated:
- `tdd_sections.generate_validation_section` / `_error_handling_section` /
  `_audit_monitoring_section` / `_performance_section` / `_security_section` /
  `_dependency_section`
- `testing_architecture.build_testing_architecture`
- `migration_assessment.build_migration_assessment`
- `exec_summary.build_executive_summary`

## Export Formats

| Format | Renderer | Notes |
|---|---|---|
| Markdown | Direct write | Source of truth for the other 3 formats |
| HTML | `export_utils.markdown_to_html` (reused) | Includes Mermaid support for any flowcharts |
| DOCX | `export_utils.write_docx` (reused) | python-docx, with raw-OOXML fallback if python-docx is unavailable |
| PDF | `tdd_export._write_tdd_pdf` (new) | ReportLab `SimpleDocTemplate` with real heading levels, bullet lists, and **paginated markdown tables** — `export_utils.write_pdf` is a single-page raw-text dump with no table support, so a dedicated renderer was required to satisfy "include diagrams and tables" |

## Validation (Phase 18F)
All 4 formats were verified end-to-end against a synthetic job matching the
repository's real `Update_mean_max` job shape:
- Markdown: written and re-read.
- HTML: parsed with `html.parser` — no structural errors.
- DOCX: opened with `python-docx`, paragraph count confirmed.
- PDF: opened with `pypdf`, page count and extracted text confirmed.

## File Structure
```
app/tiap/documentation/
  tdd_export.py     ← New: content assembly + DOCX/PDF/HTML/MD export
  tdd_sections.py    ← Phase 17D/17E section generators (reused here)
docs/architecture/
  TMA_TDD_Export_Engine.md
```

## Integration
Wired into `app/ui/tdd_page.py` as a "⬇️ Download TDD" popover button (replacing
the previously disabled placeholder button) with a job selector, a "Generate
Exports" action, and one `st.download_button` per format once generated.
