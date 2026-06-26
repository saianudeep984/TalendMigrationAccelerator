from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None


STATE_DEFAULTS = {
    "selected_job": None,
    "selected_project": None,
    "selected_lineage_node": None,
    "selected_wave": None,
    "dashboard_filters": {},
}


class DashboardStateManager:
    def __init__(self, session: Optional[Dict[str, Any]] = None) -> None:
        self.session = session if session is not None else self._session()
        self.session.setdefault("_tma_dashboard_state", dict(STATE_DEFAULTS))

    def _session(self) -> Dict[str, Any]:
        if st is not None:
            try:
                return st.session_state
            except Exception:
                pass
        return {}

    def _state(self) -> Dict[str, Any]:
        return self.session.setdefault("_tma_dashboard_state", dict(STATE_DEFAULTS))

    def get(self, key: str, default: Any = None) -> Any:
        return self._state().get(key, default)

    def set(self, key: str, value: Any) -> Any:
        self._state()[key] = value
        return value

    def update(self, **values: Any) -> Dict[str, Any]:
        self._state().update(values)
        return self.snapshot()

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._state())

    def track_page(self, page_key: str) -> bool:
        previous = self.session.get("_tma_current_page")
        self.session["_tma_previous_page"] = previous
        self.session["_tma_current_page"] = page_key
        return previous != page_key


@st.cache_resource(show_spinner=False)
def get_state_manager() -> DashboardStateManager:
    return DashboardStateManager()
