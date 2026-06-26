# TMA TDD Generator — Quality & Advanced Sections

## Overview
Extends the existing `tdd_page.py` Technical Design Document with live, per-job
generation for the sections that previously rendered only a placeholder text area.

## Sections Wired (Phase 17D–17F)

| Section | Generator | Module |
|---|---|---|
| Validation | `generate_validation_section` | `app.tiap.documentation.tdd_sections` |
| Error Handling | `generate_error_handling_section` | `app.tiap.documentation.tdd_sections` |
| Audit & Monitoring | `generate_audit_monitoring_section` | `app.tiap.documentation.tdd_sections` |
| Performance | `generate_performance_section` | `app.tiap.documentation.tdd_sections` |
| Security | `generate_security_section` | `app.tiap.documentation.tdd_sections` |
| Dependency Architecture | `generate_dependency_section` | `app.tiap.documentation.tdd_sections` |
| Testing | `build_testing_architecture` (reused) | `app.tiap.testing.testing_architecture` |
| Migration Assessment | `build_migration_assessment` (reused) | `app.tiap.migration_assessment.migration_assessment` |
| AI Summary | `build_executive_summary` (reused) | `app.tiap.exec_summary.exec_summary` |

`tdd_sections.py` performs lightweight, component-level detection directly against
`job_data["components"]` (component-type presence, parameter scans for nullability,
SSL, DIE_ON_ERROR, LKUP_PARALLELIZE, etc.) — the same detection style used in the
project's static architecture docs under `docs/architecture/`, but live and reusable
across any job rather than a one-off analysis.

Testing, Migration Assessment, and AI Summary sections do not duplicate logic —
they call directly into the Phase 14/15/16 modules and summarize the result, with a
pointer to the dedicated full page for detail.

## Not Covered
"Transformations" (section index 5) remains a placeholder — it was not named in any
Phase 17 sub-phase and no existing generator targets it specifically.

## Integration
All sections wired into `app/ui/tdd_page.py`'s section dispatch loop, each with its
own job selector (`_select_job` helper) consistent with the existing live sections
(Job/Source/Target Architecture, Mapping).
