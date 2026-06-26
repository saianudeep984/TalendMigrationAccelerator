from __future__ import annotations

import streamlit as st

from app.performance.cache_manager import get_cache_manager
from app.performance.dashboard_state_manager import get_state_manager
from app.performance.page_loader import get_page_loader


def render_performance_dashboard() -> None:
    from app.ui.design_system_v2 import std_page_header, section_header
    std_page_header("⚡", "Performance & Cache", "Cache management and performance diagnostics")
    cache = get_cache_manager()
    metrics = cache.metrics_snapshot()
    cols = st.columns(5)
    cols[0].metric("Cache Hits", metrics["cache_hits"])
    cols[1].metric("Cache Misses", metrics["cache_misses"])
    cols[2].metric("Efficiency", f"{metrics['cache_efficiency']:.0%}")
    cols[3].metric("Cache Size", metrics["cache_size_bytes"])
    cols[4].metric("Current Page", get_state_manager().session.get("_tma_current_page", "home"))
    section_header("Analysis Cache")
    st.json(metrics["namespaces"].get("analysis", {}))
    section_header("Lazy Pages")
    st.json(get_page_loader().metrics())
    section_header("Dashboard State")
    st.json(get_state_manager().snapshot())


render = render_performance_dashboard
