from app.performance.cache_invalidator import CacheInvalidationEngine
from app.performance.cache_manager import AnalysisCacheManager
from app.performance.cache_metrics import CacheMetricsEngine
from app.performance.materialized_cache import MaterializedAnalysisCache


def test_navigation_does_not_invalidate_cache(tmp_path):
    session = {}
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), session)
    cache.set("analysis", "dependency_graph", {"nodes": []})

    changed = CacheInvalidationEngine(cache).evaluate(zip_fingerprint="zip-a", state=session)
    same = CacheInvalidationEngine(cache).evaluate(zip_fingerprint="zip-a", state=session)

    assert changed is False
    assert same is False
    assert cache.get("analysis", "dependency_graph") == {"nodes": []}


def test_new_zip_invalidates_cache(tmp_path):
    session = {"_tma_zip_fingerprint": "zip-a"}
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), session)
    cache.set("analysis", "dependency_graph", {"nodes": []})

    changed = CacheInvalidationEngine(cache).evaluate(zip_fingerprint="zip-b", state=session)

    assert changed is True
    assert cache.get("analysis", "dependency_graph") is None
