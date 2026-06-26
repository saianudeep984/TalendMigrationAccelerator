import time

from app.performance.cache_manager import AnalysisCacheManager
from app.performance.cache_metrics import CacheMetricsEngine
from app.performance.graph_cache import GraphCache
from app.performance.graph_virtualizer import GraphVirtualizer
from app.performance.materialized_cache import MaterializedAnalysisCache


def _large_graph(nodes=1000, edges=10000):
    return {
        "nodes": [{"id": f"n{i}"} for i in range(nodes)],
        "edges": [{"source": f"n{i % nodes}", "target": f"n{(i + 1) % nodes}"} for i in range(edges)],
    }


def test_graph_virtualizer_renders_visible_subgraph_under_2_seconds():
    graph = _large_graph(1200, 10000)
    virtualizer = GraphVirtualizer(max_nodes=80, max_edges=160)
    start = time.perf_counter()
    visible = virtualizer.visible_subgraph(graph, roots=["n0"], depth=3)
    elapsed = time.perf_counter() - start

    assert len(visible["nodes"]) <= 80
    assert len(visible["edges"]) <= 160
    assert visible["hidden_node_count"] > 0
    assert elapsed < 2.0


def test_expand_on_demand_depth_navigation():
    graph = {
        "nodes": [{"id": f"n{i}"} for i in range(6)],
        "edges": [
            {"source": "n0", "target": "n1"},
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
            {"source": "n4", "target": "n5"},
        ],
    }
    virtualizer = GraphVirtualizer(max_nodes=10, max_edges=10)

    depth_one = virtualizer.visible_subgraph(graph, roots=["n0"], depth=1)
    expanded = virtualizer.expand(graph, "n1", [n["id"] for n in depth_one["nodes"]], depth=2)

    assert {n["id"] for n in depth_one["nodes"]} == {"n0", "n1"}
    assert "n3" in {n["id"] for n in expanded["nodes"]}
    assert "n4" not in {n["id"] for n in expanded["nodes"]}


def test_graph_cache_reuses_lineage_dependency_impact_graphs(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    graph_cache = GraphCache(cache)
    calls = {"lineage": 0, "dependency": 0, "impact": 0}

    lineage = graph_cache.lineage("fp-l", lambda: calls.__setitem__("lineage", calls["lineage"] + 1) or {"nodes": [], "edges": []})
    lineage_again = graph_cache.lineage("fp-l", lambda: {"wrong": True})
    dependency = graph_cache.dependency("fp-d", lambda: calls.__setitem__("dependency", calls["dependency"] + 1) or {"nodes": ["a"], "edges": []})
    impact = graph_cache.impact("fp-i", lambda: calls.__setitem__("impact", calls["impact"] + 1) or {"nodes": ["b"], "edges": []})

    assert lineage == lineage_again
    assert dependency["nodes"] == ["a"]
    assert impact["nodes"] == ["b"]
    assert calls == {"lineage": 1, "dependency": 1, "impact": 1}


def test_graph_cache_caches_visible_views(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    graph_cache = GraphCache(cache)
    graph = _large_graph(100, 200)

    first = graph_cache.visible("lineage", graph, roots=["n0"], depth=2, max_nodes=20, max_edges=40)
    second = graph_cache.visible("lineage", graph, roots=["n0"], depth=2, max_nodes=20, max_edges=40)

    assert first == second
    assert cache.metrics_snapshot()["cache_hits"] >= 1
