"""Performance, lazy loading, and cache services."""

from app.performance.background_processor import BackgroundAnalysisEngine
from app.performance.cache_manager import AnalysisCacheManager, get_cache_manager
from app.performance.dashboard_state_manager import DashboardStateManager, get_state_manager
from app.performance.data_loader import PerformanceAwareDataLoader
from app.performance.graph_cache import GraphCache
from app.performance.graph_virtualizer import GraphVirtualizer
from app.performance.incremental_analysis import IncrementalAnalysisFramework
from app.performance.lazy_loader import LazyLoader, LazyTabRegistry, lazy_tabs, lazy_value
from app.performance.page_loader import PageLoader, get_page_loader
from app.performance.pagination import PageResult, ServerSidePaginator
from app.performance.progress_tracker import ProgressTracker
from app.performance.task_queue import AnalysisTaskQueue, AnalysisTask
from app.performance.virtualized_grid import VirtualizedGrid, VirtualGridWindow

__all__ = [
    "AnalysisCacheManager",
    "AnalysisTask",
    "AnalysisTaskQueue",
    "BackgroundAnalysisEngine",
    "DashboardStateManager",
    "GraphCache",
    "GraphVirtualizer",
    "IncrementalAnalysisFramework",
    "LazyLoader",
    "LazyTabRegistry",
    "PageLoader",
    "PageResult",
    "PerformanceAwareDataLoader",
    "ProgressTracker",
    "ServerSidePaginator",
    "VirtualGridWindow",
    "VirtualizedGrid",
    "get_cache_manager",
    "get_page_loader",
    "get_state_manager",
    "lazy_tabs",
    "lazy_value",
]
