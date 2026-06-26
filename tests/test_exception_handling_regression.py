"""
Exception handling regression suite (F7.5).
Locks the severity classification table and guards the Streamlit UI
integration points (F7.2/F7.4) against regressions.
"""

import ast
import logging

from app.utils.logger import Severity, classify_severity, handle_exception, logger

UI_FILES = ["app/ui/streamlit_app.py", "app/ui/streamlit_app_v2.py"]


# --- Classification table locked (golden values) ---

def test_classification_table_locked():
    cases = {
        FileNotFoundError: Severity.WARNING,
        TimeoutError: Severity.WARNING,
        ConnectionError: Severity.WARNING,
        ValueError: Severity.ERROR,
        KeyError: Severity.ERROR,
        TypeError: Severity.ERROR,
        AttributeError: Severity.ERROR,
        OSError: Severity.ERROR,
        MemoryError: Severity.CRITICAL,
        RecursionError: Severity.CRITICAL,
        SystemError: Severity.CRITICAL,
        RuntimeError: Severity.ERROR,  # unmatched -> default
        StopIteration: Severity.ERROR,  # unmatched -> default
    }
    for exc_type, expected in cases.items():
        exc = exc_type() if exc_type is not KeyError else KeyError("k")
        assert classify_severity(exc) == expected, exc_type


def test_logger_name_is_stable():
    assert logger.name == "tma"


# --- No bare except regression (F7.2) ---

def test_no_bare_except_in_ui_files():
    for path in UI_FILES:
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                assert node.type is not None, f"bare except reintroduced in {path}:{node.lineno}"


# --- Centralized utility actually wired into UI files (F7.3/F7.4) ---

def test_ui_files_import_centralized_handler():
    for path in UI_FILES:
        src = open(path, encoding="utf-8").read()
        assert "from app.utils.logger import handle_exception, logger" in src


def test_ui_files_use_handle_exception_for_generation_steps():
    for path in UI_FILES:
        src = open(path, encoding="utf-8").read()
        assert 'handle_exception(excel_err, "Excel report generation")' in src
        assert 'handle_exception(patch_err, "Migration patch generation")' in src
        assert 'handle_exception(dep_err, "Dependency graph export")' in src


def test_ui_files_do_not_reintroduce_local_logging_import():
    for path in UI_FILES:
        src = open(path, encoding="utf-8").read()
        assert "import logging" not in src


# --- Behavioral regression: handle_exception side effects ---

def test_handle_exception_no_ui_no_streamlit_dependency():
    # Must work headlessly without raising even if streamlit isn't running.
    sev = handle_exception(ValueError("x"), "ctx", show_ui=False)
    assert sev == Severity.ERROR


def test_handle_exception_logs_exact_context_and_severity(caplog):
    with caplog.at_level(logging.ERROR, logger="tma"):
        handle_exception(ValueError("boom"), "regression ctx", show_ui=False)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("regression ctx" in m and "ERROR" in m and "boom" in m for m in msgs)


def test_handle_exception_critical_logs_traceback(caplog):
    with caplog.at_level(logging.CRITICAL, logger="tma"):
        try:
            raise MemoryError("oom")
        except MemoryError as e:
            handle_exception(e, "alloc", show_ui=False)
    assert any(r.exc_info for r in caplog.records)
