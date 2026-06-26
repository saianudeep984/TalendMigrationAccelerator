import time

from app.performance.background_processor import BackgroundAnalysisEngine
from app.performance.cache_manager import AnalysisCacheManager
from app.performance.cache_metrics import CacheMetricsEngine
from app.performance.materialized_cache import MaterializedAnalysisCache
from app.performance.progress_tracker import ProgressTracker
from app.performance.task_queue import AnalysisTaskQueue


def test_background_processor_runs_analysis_in_parallel(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    queue = AnalysisTaskQueue()
    engine = BackgroundAnalysisEngine(max_workers=5, cache=cache, queue=queue)

    def slow(value):
        time.sleep(0.08)
        return value

    producers = {
        "lineage_analysis": lambda: slow("lineage"),
        "impact_analysis": lambda: slow("impact"),
        "framework_analysis": lambda: slow("framework"),
        "upgrade_advisor": lambda: slow("upgrade"),
        "migration_intelligence": lambda: slow("migration"),
    }
    start = time.perf_counter()
    results = engine.run_parallel(producers)
    elapsed = time.perf_counter() - start

    assert results["lineage_analysis"] == "lineage"
    assert set(results) == set(producers)
    assert elapsed < 0.30
    assert all(task.status == "completed" for task in queue.tasks())


def test_progress_tracker_reports_pending_running_completed():
    queue = AnalysisTaskQueue()
    pending = queue.enqueue("lineage_analysis")
    running = queue.enqueue("impact_analysis")
    done = queue.enqueue("framework_analysis")
    queue.mark_running(running.task_id)
    queue.mark_running(done.task_id)
    queue.mark_completed(done.task_id, result={"ok": True})

    snapshot = ProgressTracker(queue).snapshot()

    assert snapshot["pending"] == 1
    assert snapshot["running"] == 1
    assert snapshot["completed"] == 1
    assert snapshot["total"] == 3
    assert pending.task_id in snapshot["tasks"]


def test_background_processor_reuses_cache_without_reanalysis(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    engine = BackgroundAnalysisEngine(max_workers=2, cache=cache, queue=AnalysisTaskQueue())
    calls = {"count": 0}

    def build():
        calls["count"] += 1
        return {"value": calls["count"]}

    assert engine.run_parallel({"impact_analysis": build}, {"impact_analysis": "fp"})["impact_analysis"] == {"value": 1}
    assert engine.run_parallel({"impact_analysis": build}, {"impact_analysis": "fp"})["impact_analysis"] == {"value": 1}
    assert calls["count"] == 1
