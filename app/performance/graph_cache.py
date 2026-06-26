from __future__ import annotations

from typing import Any, Callable, Optional

from app.performance.cache_manager import AnalysisCacheManager, get_cache_manager
from app.performance.graph_virtualizer import GraphVirtualizer


class GraphCache:
    """Cache facade for lineage, dependency, impact, and virtualized graph views."""

    def __init__(self, cache: Optional[AnalysisCacheManager] = None) -> None:
        self.cache = cache or get_cache_manager()

    def get_or_build(self, graph_type: str, fingerprint: str, builder: Callable[[], Any]) -> Any:
        return self.cache.get_or_compute(f"graph:{graph_type}", builder, "analysis", True, fingerprint)

    def lineage(self, fingerprint: str, builder: Callable[[], Any]) -> Any:
        return self.get_or_build("lineage", fingerprint, builder)

    def dependency(self, fingerprint: str, builder: Callable[[], Any]) -> Any:
        return self.get_or_build("dependency", fingerprint, builder)

    def impact(self, fingerprint: str, builder: Callable[[], Any]) -> Any:
        return self.get_or_build("impact", fingerprint, builder)

    def visible(
        self,
        graph_type: str,
        graph: Any,
        roots: list[str] | None = None,
        depth: int = 1,
        max_nodes: int = 250,
        max_edges: int = 500,
    ) -> Any:
        fp = self.cache.fingerprint("visible", graph_type, roots, depth, max_nodes, max_edges, graph)
        return self.cache.get_or_compute(
            f"graph_visible:{graph_type}:{fp}",
            lambda: GraphVirtualizer(max_nodes=max_nodes, max_edges=max_edges).visible_subgraph(graph, roots, depth),
            "ui",
            False,
            fp,
        )
