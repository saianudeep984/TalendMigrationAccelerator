"""
Centralized exception handling for Streamlit pages (F7.3/F7.4).

Provides a single entry point — handle_exception() — that classifies an
exception's severity, logs it at the matching level, and routes user-facing
feedback to the correct Streamlit widget (st.info/st.warning/st.error), so
every page reports failures consistently instead of ad-hoc try/except blocks.
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("tma")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


class Severity(Enum):
    """Error severity bands, ordered low to high."""
    INFO = "INFO"          # expected/recoverable, no action needed
    WARNING = "WARNING"    # degraded feature, rest of flow continues
    ERROR = "ERROR"        # current operation failed, user must retry/fix input
    CRITICAL = "CRITICAL"  # unrecoverable, app/session state may be inconsistent


# Exception types routed to each severity by default. First match wins;
# unmatched exceptions default to ERROR.
_SEVERITY_RULES = [
    (Severity.WARNING, (FileNotFoundError, TimeoutError, ConnectionError)),
    (Severity.ERROR, (ValueError, KeyError, TypeError, AttributeError, OSError)),
    (Severity.CRITICAL, (MemoryError, RecursionError, SystemError)),
]

_LOG_LEVEL = {
    Severity.INFO: logging.INFO,
    Severity.WARNING: logging.WARNING,
    Severity.ERROR: logging.ERROR,
    Severity.CRITICAL: logging.CRITICAL,
}


def classify_severity(exc: BaseException) -> Severity:
    """Map an exception instance to a Severity band by type."""
    for severity, types in _SEVERITY_RULES:
        if isinstance(exc, types):
            return severity
    return Severity.ERROR


def handle_exception(
    exc: BaseException,
    context: str,
    severity: Optional[Severity] = None,
    user_message: Optional[str] = None,
    show_ui: bool = True,
    raise_on_critical: bool = False,
) -> Severity:
    """
    Single entry point for Streamlit pages to report an exception.

    Args:
        exc: the caught exception instance.
        context: short description of what was being attempted,
                 e.g. "Excel report generation".
        severity: override auto-classification.
        user_message: override the default user-facing message.
        show_ui: render feedback via Streamlit (st.info/warning/error);
                 set False for headless/background calls.
        raise_on_critical: re-raise the original exception after logging
                            when severity is CRITICAL.

    Returns:
        The resolved Severity, so callers can branch on it if needed.
    """
    sev = severity or classify_severity(exc)
    logger.log(_LOG_LEVEL[sev], "[%s] %s: %s", context, sev.value, exc, exc_info=(sev == Severity.CRITICAL))

    if show_ui:
        try:
            import streamlit as st
        except ImportError:
            st = None
        if st is not None:
            msg = user_message or f"{context} failed: {exc}"
            if sev == Severity.INFO:
                st.info(msg)
            elif sev == Severity.WARNING:
                st.warning(msg)
            elif sev == Severity.ERROR:
                st.error(msg)
            else:
                st.error(f"Critical error in {context}. Please reload and try again.\n\n{exc}")

    if sev == Severity.CRITICAL and raise_on_critical:
        raise exc

    return sev
