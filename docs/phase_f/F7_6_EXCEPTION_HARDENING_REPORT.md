# F7.6 Exception Hardening Report

## Scope
`app/ui/streamlit_app.py`, `app/ui/streamlit_app_v2.py`, and the new
centralized utility `app/utils/logger.py`.

## What changed (F7.1–F7.5)

| Task | Outcome |
|---|---|
| F7.1 Scan | 10 bare `except:` clauses found, both in the two Streamlit page files. |
| F7.2 Fix | All 10 replaced with `except Exception as e:` + logging. 0 bare excepts remain. |
| F7.3 Utility | `app/utils/logger.py` (was an empty placeholder) implements `handle_exception()`. |
| F7.4 Routing | `Severity` enum (INFO/WARNING/ERROR/CRITICAL) + type-based `classify_severity()`; routes to matching `logger.log()` level and `st.info/warning/error`. |
| F7.5 Regression | 9 new tests lock the classification table, ban bare-except reintroduction, and verify both UI files are wired to the centralized handler. |

## Centralized handler adoption

| File | Sites using `handle_exception()` | Sites using direct `logger.debug` (intentional, non-user-facing cleanup) |
|---|---|---|
| app/ui/streamlit_app.py | 4 | 1 |
| app/ui/streamlit_app_v2.py | 4 | 1 |

Generation-step failures (Excel report, migration patch, dependency graph
export) and AI-recommendation failures now route through `handle_exception`,
giving consistent log level + user feedback instead of silent `pass` or
ad-hoc `logger.warning` calls.

## Severity classification table (locked by regression tests)

| Severity | Exception types |
|---|---|
| WARNING | FileNotFoundError, TimeoutError, ConnectionError |
| ERROR (default) | ValueError, KeyError, TypeError, AttributeError, OSError, and any unmatched type |
| CRITICAL | MemoryError, RecursionError, SystemError |

## Test coverage added

| File | Tests |
|---|---|
| tests/test_exception_utility.py | 10 |
| tests/test_exception_handling_regression.py | 9 |
| **Total new** | **19** |

## Code added

| File | LOC |
|---|---|
| app/utils/logger.py | 101 |
| tests/test_exception_utility.py | 60 |
| tests/test_exception_handling_regression.py | 95 |

## Validation
Full suite: **200/200 PASSED** (181 pre-existing + 19 new).
AST check confirms zero bare `except:` in both hardened files.

## Out of scope / residual risk
A broader repo-wide AST scan (informational, not actioned) flags 85
`except Exception:` blocks elsewhere in the codebase that catch broadly
without logging — outside the bare-except scope of F7.1/F7.2 and not
modified in this phase. Recommend a follow-up phase to migrate those
call sites onto `handle_exception()` for consistent observability.
