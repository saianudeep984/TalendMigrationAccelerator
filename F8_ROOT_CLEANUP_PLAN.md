# F8.1 Repository Root Audit & Cleanup Plan

## Findings

### A. Generated/transient artifacts → DELETE
| Path | Reason |
|---|---|
| `__pycache__/`, `app/__pycache__/`, `app/**/__pycache__/`, `tests/__pycache__/`, `scripts/__pycache__/`, `pytest_pkg/__pycache__/` | Bytecode cache, regenerable |
| `output/` (dependency_graph_data.json, dependency_summary.json, migration_patch.json) | Run artifacts from a prior job execution, not source |
| `pre_migration_temp/` | Scratch dir from a prior migration run (Test_Plugin_Max_values + jobInfo.properties) |
| `migration_report.xlsx` | Generated output, not source |
| `temp_repository/` | Vendored sample Talend job + jars/lib (6.3M), not part of app source — should live under `sample_projects/` or be excluded, not at root |

### B. Superseded/duplicate docs → DELETE or CONSOLIDATE
| Path | Reason |
|---|---|
| `ASSISTED_MIGRATION_WORKFLOW.md`, `ENTERPRISE_AUTOMATION_ARCHITECTURE.md`, `ENTERPRISE_MIGRATION_STRATEGY.md`, `README_AUTOMATION_WORKFLOW.txt`, `README_ENTERPRISE.txt`, `TALEND_MIGRATION_AUTOMATION.md` | 6 overlapping docs describing the same enterprise workflow/architecture — content largely duplicated. Consolidate into single `ARCHITECTURE.md`. |
| `PHASE2_REMAINING_IMPLEMENTATION.md`, `PHASE2_TEMPLATE_ENGINE_COMPLETED.txt`, `TEMPLATE_RECONSTRUCTION_IMPLEMENTATION.md`, `TEMPLATE_RECONSTRUCTION_ROADMAP.md` | 4 historical phase-tracking notes for completed work — superseded by current code state. Archive or delete. |
| `V22_PROJECT_REGISTRATION_FIX.txt`, `V24_PROJECT_SKELETON_FIX.txt`, `SAFE_IMPORT_STRATEGY.txt` | Point-in-time bugfix notes, superseded by current `VERSION` (v5). Archive or delete. |
| `column_mapping_phase1_report.md`, `TEST_VALIDATION_REPORT.md`, `F6_CLEANUP_REPORT.md` | Phase/audit reports — keep under `docs/reports/` instead of root. |

### C. Dead config/dup files → VERIFY THEN DELETE
| Path | Reason |
|---|---|
| `pytest_shim.py` + `pytest_pkg/` | Both implement pytest fallback shims — likely redundant now that `pytest` is an installed dependency (confirmed in F6.5). Needs reference check before removal. |
| `requirements-lock.txt` | Diverges from `requirements.txt` (14 vs 16 lines) — stale lockfile; regenerate or delete. |

### D. Keep as-is
`main.py`, `main_v2.py` (distinct entrypoints — classic vs wizard UI), `app/`, `tests/`, `config/`, `docs/`, `assets/`, `templates/`, `sample_projects/`, `scripts/`, `requirements.txt`, `pytest.ini`, `VERSION`, `README.md`, `run_tests.py`.

## Proposed Actions (ordered)
1. Delete all `__pycache__` dirs.
2. Delete `output/`, `pre_migration_temp/`, `migration_report.xlsx` (regenerable run artifacts).
3. Relocate `temp_repository/` contents into `sample_projects/` or remove if duplicated there; confirm no code references `temp_repository` path before deletion.
4. Verify zero references to `pytest_shim.py`/`pytest_pkg/`, then delete if dead (same method as F6.4).
5. Consolidate the 6 architecture/workflow docs → 1 `ARCHITECTURE.md`; delete originals.
6. Archive/delete the 7 phase-tracking and point-fix `.txt`/`.md` notes (B above).
7. Move report files (`TEST_VALIDATION_REPORT.md`, `F6_CLEANUP_REPORT.md`, `column_mapping_phase1_report.md`) to `docs/reports/`.
8. Regenerate or delete `requirements-lock.txt`.
9. Re-run F6.5-style validation (py_compile + pytest + entrypoint import) after each deletion batch.

## Risk Notes
- Steps 1–2 zero risk (generated artifacts).
- Step 3 needs reference grep first (jar/sample paths may be hardcoded in tests or config).
- Step 4 needs same zero-reference verification protocol as F6.4 before deletion.
- Steps 5–7 are documentation-only, zero code risk.
