import sys
import types

from app.performance.dashboard_state_manager import DashboardStateManager
from app.performance.lazy_loader import LazyLoader, LazyTabRegistry, lazy_tabs
from app.performance.page_loader import PageLoader


def test_lazy_loader_imports_only_when_called():
    module = types.ModuleType("lazy_test_module")
    module.render = lambda: "loaded"
    sys.modules["lazy_test_module"] = module
    loader = LazyLoader()

    assert loader.loaded_modules() == []
    assert loader.call("lazy_test_module") == "loaded"
    assert loader.loaded_modules() == ["lazy_test_module"]


def test_page_loader_tracks_current_page_and_preserves_state():
    session = {}
    state = DashboardStateManager(session)
    page_loader = PageLoader(state=state, register_defaults=False)
    page_loader.register("demo", "lazy_test_module", "render")

    assert page_loader.render("demo") == "loaded"
    assert session["_tma_current_page"] == "demo"
    assert page_loader.metrics()["demo"]["initialized"] is True


def test_page_loader_registers_dashboard_defaults_without_importing():
    page_loader = PageLoader(register_defaults=True)

    assert page_loader.has("job_analysis")
    assert page_loader.has("migration_intelligence")
    assert page_loader.loader.loaded_modules() == []


def test_lazy_tabs_execute_only_active_payload():
    session = {}
    calls = {"summary": 0, "lineage": 0, "impact": 0}
    tabs = LazyTabRegistry(session)
    for key in calls:
        tabs.register(key, lambda key=key: calls.__setitem__(key, calls[key] + 1) or key)

    assert tabs.render_active("job360_tab", active="lineage") == "lineage"
    assert calls == {"summary": 0, "lineage": 1, "impact": 0}
    assert session["job360_tab"] == "lineage"


def test_lazy_tabs_helper():
    calls = []
    result = lazy_tabs("migration_tab", {"waves": lambda: calls.append("waves") or 1, "risks": lambda: calls.append("risks") or 2}, active="risks", session={})

    assert result == 2
    assert calls == ["risks"]
