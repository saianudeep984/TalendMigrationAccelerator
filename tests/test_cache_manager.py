from app.performance.cache_manager import AnalysisCacheManager
from app.performance.cache_metrics import CacheMetricsEngine
from app.performance.materialized_cache import MaterializedAnalysisCache
from app.performance.analysis_restore import AnalysisRestoreEngine


def test_cache_manager_reuses_analysis_results(tmp_path):
    cache = AnalysisCacheManager(
        materialized=MaterializedAnalysisCache(tmp_path),
        metrics=CacheMetricsEngine(),
        session={},
    )
    calls = {"count": 0}

    def build():
        calls["count"] += 1
        return {"ready": True}

    assert cache.cache_analysis("readiness_analysis", build) == {"ready": True}
    assert cache.cache_analysis("readiness_analysis", build) == {"ready": True}
    assert calls["count"] == 1
    assert cache.metrics_snapshot()["cache_hits"] >= 1


def test_materialized_restore_to_session(tmp_path):
    session = {}
    cache = AnalysisCacheManager(
        materialized=MaterializedAnalysisCache(tmp_path),
        metrics=CacheMetricsEngine(),
        session=session,
    )
    cache.set("analysis", "impact_analysis", {"impact": 1}, persist=True)

    restored = AnalysisRestoreEngine(cache).restore_to_session({"impact_analysis": "impact_intelligence"})

    assert restored["impact_analysis"] == {"impact": 1}
    assert session["impact_intelligence"] == {"impact": 1}
    assert (tmp_path / "analysis_cache.json").exists()


def test_cache_fingerprint_change_recomputes(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    calls = {"count": 0}

    def build():
        calls["count"] += 1
        return {"version": calls["count"]}

    assert cache.cache_analysis("framework_analysis", build, "fp-a") == {"version": 1}
    assert cache.cache_analysis("framework_analysis", build, "fp-a") == {"version": 1}
    assert cache.cache_analysis("framework_analysis", build, "fp-b") == {"version": 2}
    assert calls["count"] == 2


def test_materialized_cache_respects_fingerprint(tmp_path):
    materialized = MaterializedAnalysisCache(tmp_path)
    materialized.set_analysis("analysis:lineage_analysis", {"nodes": 1}, "lineage-a")

    assert materialized.get_analysis("analysis:lineage_analysis", "lineage-a") == {"nodes": 1}
    assert materialized.get_analysis("analysis:lineage_analysis", "lineage-b") is None
