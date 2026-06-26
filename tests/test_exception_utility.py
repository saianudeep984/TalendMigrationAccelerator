import logging

import pytest

from app.utils.logger import Severity, classify_severity, handle_exception


def test_classify_warning_types():
    assert classify_severity(FileNotFoundError("x")) == Severity.WARNING
    assert classify_severity(TimeoutError("x")) == Severity.WARNING
    assert classify_severity(ConnectionError("x")) == Severity.WARNING


def test_classify_error_types():
    assert classify_severity(ValueError("x")) == Severity.ERROR
    assert classify_severity(KeyError("x")) == Severity.ERROR
    assert classify_severity(TypeError("x")) == Severity.ERROR
    assert classify_severity(AttributeError("x")) == Severity.ERROR
    assert classify_severity(OSError("x")) == Severity.ERROR


def test_classify_critical_types():
    assert classify_severity(MemoryError()) == Severity.CRITICAL
    assert classify_severity(RecursionError()) == Severity.CRITICAL


def test_classify_unmatched_defaults_to_error():
    assert classify_severity(RuntimeError("x")) == Severity.ERROR


def test_handle_exception_returns_classified_severity():
    sev = handle_exception(ValueError("bad"), "test context", show_ui=False)
    assert sev == Severity.ERROR


def test_handle_exception_severity_override():
    sev = handle_exception(ValueError("bad"), "test context", severity=Severity.WARNING, show_ui=False)
    assert sev == Severity.WARNING


def test_handle_exception_logs_at_matching_level(caplog):
    with caplog.at_level(logging.WARNING, logger="tma"):
        handle_exception(FileNotFoundError("missing.txt"), "file load", show_ui=False)
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_handle_exception_critical_raises_when_requested():
    with pytest.raises(MemoryError):
        handle_exception(MemoryError(), "alloc", show_ui=False, raise_on_critical=True)


def test_handle_exception_critical_does_not_raise_by_default():
    sev = handle_exception(MemoryError(), "alloc", show_ui=False)
    assert sev == Severity.CRITICAL


def test_handle_exception_no_streamlit_does_not_raise():
    # show_ui=False must never require streamlit to be importable/running.
    sev = handle_exception(KeyError("k"), "lookup", show_ui=False)
    assert sev == Severity.ERROR
