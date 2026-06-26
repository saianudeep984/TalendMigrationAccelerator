from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from app.performance.dashboard_state_manager import DashboardStateManager, get_state_manager
from app.performance.lazy_loader import LazyLoader
import streamlit as st


DEFAULT_PAGE_REGISTRY = {
    "executive_dashboard": ("app.ui.executive_dashboard_page", "render_executive_dashboard_page", "Executive Dashboard"),
    "job_analysis": ("app.ui.job_analysis_page", "render_job_analysis_page", "Job360"),
    "migration_intelligence": ("app.ui.migration_intelligence_dashboard", "render_migration_intelligence_dashboard", "Migration Intelligence"),
    "impact_intelligence": ("app.ui.impact_intelligence_dashboard", "render_impact_intelligence_dashboard", "Impact Intelligence"),
    "architecture_dashboard": ("app.ui.architecture_intelligence_dashboard", "render_architecture_intelligence_dashboard", "Architecture Dashboard"),
    "upgrade_advisor": ("app.ui.upgrade_advisor_dashboard", "render_upgrade_advisor_dashboard", "Upgrade Advisor"),
    "framework_intel": ("app.ui.framework_intelligence_dashboard", "render_framework_intelligence_dashboard", "Framework Dashboard"),
    "portfolio_dashboard": ("app.ui.portfolio_dashboard", "render_portfolio_dashboard", "Portfolio Dashboard"),
    "performance_dashboard": ("app.ui.performance_dashboard", "render_performance_dashboard", "Performance Dashboard"),
}


@dataclass
class PageDefinition:
    key: str
    module_path: str
    callable_name: str = "render"
    title: str = ""
    initialized: bool = False
    last_loaded_seconds: float = 0.0
    render_count: int = 0


class PageLoader:
    """Central page registry with dynamic module loading and state retention."""

    def __init__(
        self,
        loader: Optional[LazyLoader] = None,
        state: Optional[DashboardStateManager] = None,
        register_defaults: bool = True,
    ) -> None:
        self.loader = loader or LazyLoader()
        self.state = state or get_state_manager()
        self.registry: Dict[str, PageDefinition] = {}
        if register_defaults:
            self.register_defaults()

    def register_defaults(self) -> None:
        for key, (module_path, callable_name, title) in DEFAULT_PAGE_REGISTRY.items():
            if key not in self.registry:
                self.register(key, module_path, callable_name, title)

    def register(self, key: str, module_path: str, callable_name: str = "render", title: str = "") -> None:
        self.registry[key] = PageDefinition(key, module_path, callable_name, title)

    def has(self, key: str) -> bool:
        return key in self.registry

    def load(self, key: str) -> Callable[..., Any]:
        page = self.registry[key]
        start = time.perf_counter()
        target = self.loader.resolve(page.module_path, page.callable_name)
        page.initialized = True
        page.last_loaded_seconds = time.perf_counter() - start
        return target

    def render(self, key: str, *args: Any, **kwargs: Any) -> Any:
        if key not in self.registry:
            raise KeyError(f"Unknown lazy page: {key}")
        changed = self.state.track_page(key)
        self.state.session["_tma_navigation_changed"] = changed
        page = self.registry[key]
        page.render_count += 1
        return self.load(key)(*args, **kwargs)

    def metrics(self) -> Dict[str, Any]:
        return {
            key: {
                "initialized": page.initialized,
                "last_loaded_seconds": page.last_loaded_seconds,
                "module": page.module_path,
                "render_count": page.render_count,
            }
            for key, page in self.registry.items()
        }


@st.cache_resource(show_spinner=False)
def get_page_loader() -> PageLoader:
    return PageLoader()
