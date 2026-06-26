import time

from app.performance.cache_manager import AnalysisCacheManager
from app.performance.cache_metrics import CacheMetricsEngine
from app.performance.data_loader import PerformanceAwareDataLoader
from app.performance.materialized_cache import MaterializedAnalysisCache


def test_incremental_loader_batches_large_projects():
    loader = PerformanceAwareDataLoader(page_size=500)
    jobs = list(range(5000))

    batches = list(loader.batches(jobs))

    assert len(batches) == 10
    assert batches[0] == list(range(500))


def test_incremental_loader_slices_jobs_components_lineage_dependencies():
    loader = PerformanceAwareDataLoader(page_size=2)
    jobs = [
        {"job_data": {"job_name": "a", "components": [1, 2, 3]}, "dependencies": {"x": ["b"]}},
        {"job_data": {"job_name": "b", "components": [4]}, "dependencies": {}},
        {"job_data": {"job_name": "c", "components": [5]}, "dependencies": {}},
    ]

    assert [j["job_data"]["job_name"] for j in loader.jobs(jobs, 1)] == ["c"]
    assert loader.components(jobs, 1) == [3, 4]
    assert loader.lineage_edges({"edges": ["e1", "e2", "e3"]}, 1) == ["e3"]
    assert loader.dependencies(jobs, 0)[0]["job"] == "a"


def test_cache_benchmark_metrics_for_100_to_5000_jobs(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    sizes = [100, 500, 1000, 5000]

    for size in sizes:
        jobs = [{"job_data": {"job_name": f"job_{i}", "components": []}} for i in range(size)]
        key = f"readiness_{size}"
        start = time.perf_counter()
        cache.cache_analysis(key, lambda jobs=jobs: {"jobs": len(jobs)}, cache.fingerprint(jobs))
        first = time.perf_counter() - start
        start = time.perf_counter()
        cache.cache_analysis(key, lambda: {"jobs": 0}, cache.fingerprint(jobs))
        second = time.perf_counter() - start
        assert second <= first

    metrics = cache.metrics_snapshot()
    assert metrics["cache_hits"] >= len(sizes)
    assert metrics["cache_efficiency"] >= 0.5
