# F6.1 Unreachable Code / Cleanup Inventory

Scope: `app/`, `scripts/`, `main_v2.py`.
Method: AST scan for code after terminal statements (return/raise/break/
continue/sys.exit) — 0 hits — plus targeted grep for constant-False guards
(`if False`, `False and ...`), which Python does not eliminate at parse
time and which the linter/AST pass above does not catch.

## Unreachable Settings implementation (deprecated, superseded)

| File | Lines | Guard | Status |
|---|---|---|---|
| app/ui/streamlit_app.py | 936–1103 (168 lines) | `if False and _sel == "settings":` | Dead. Superseded by the live `if _sel == "settings":` block at line 764 ("Assessment Configuration Hub"). Old tabbed Settings page (`tab_general, tab_scoring, tab_ollama, tab_templates, tab_environment`) is unreachable — condition always `False`. |

## Deprecated UI fragments (dead widget, constant-False guard)

| File | Lines | Guard | Status |
|---|---|---|---|
| app/ui/streamlit_app.py | 1973–1975 (3 lines) | `if False:` | Dead "custom report header" text_area widget in the Generate-step page. |
| app/ui/streamlit_app_v2.py | 599–601 (3 lines) | `if False:` | Same dead widget, v2 wizard variant. |

## Out of scope (not a dead UI/Settings path — left as-is)

| File | Line | Note |
|---|---|---|
| app/analyzers/unsupported_component_analyzer.py | 189 | `... if False else 0  # placeholder, fixed below` — a value-level conditional expression, not a code path; unrelated to UI/Settings. |

## Totals targeted for removal (F6.2)

- 1 unreachable Settings implementation: 168 lines.
- 2 deprecated UI fragments: 6 lines (3 + 3).
- **174 lines total** across 2 files.

## Verification plan

- AST parse before/after each file.
- Confirm `if _sel == "settings"` (the live block) is untouched.
- Confirm `_build_repository_report_zip` and all code after the dead block
  is preserved unchanged (it sits immediately after the dead block at
  module level, not nested inside it).
- Run full test suite.
