# F7.1 Bare-Except Scan Report

Scope: `app/`, `scripts/`, `main_v2.py` (excludes tests/, sample_projects/,
temp_repository/, pre_migration_temp/, output/).

Method: regex `^\s*except\s*:` (true bare except, no exception type bound)
cross-checked via AST `ExceptHandler` with `node.type is None`.

## Bare `except:` clauses found — 10 total, 2 files

| File | Line | Context | Body |
|---|---|---|---|
| app/ui/streamlit_app_v2.py | 287 | temp zip cleanup (finally) | `pass` |
| app/ui/streamlit_app_v2.py | 367 | AI recommendation generation | sets fallback string |
| app/ui/streamlit_app_v2.py | 619 | Excel report generation step | `pass` |
| app/ui/streamlit_app_v2.py | 633 | migration patch generation step | `pass` |
| app/ui/streamlit_app_v2.py | 641 | dependency graph export step | `pass` |
| app/ui/streamlit_app.py | 1509 | temp zip cleanup (finally) | `pass` |
| app/ui/streamlit_app.py | 1583 | AI recommendation generation | sets fallback string |
| app/ui/streamlit_app.py | 1989 | Excel report generation step | `pass` |
| app/ui/streamlit_app.py | 2003 | migration patch generation step | `pass` |
| app/ui/streamlit_app.py | 2011 | dependency graph export step | `pass` |

All 10 instances swallow errors silently (`pass` or no diagnostic output) and
catch every exception type including `SystemExit`/`KeyboardInterrupt`.

Note: a broader AST scan also flagged 77 `except Exception:` blocks without
logging across the repo; those are out of scope for F7.1/F7.2 (which target
bare `except:` specifically) and are not modified here.
