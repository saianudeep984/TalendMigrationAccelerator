from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Mapping, Optional

from app.performance.cache_manager import AnalysisCacheManager, get_cache_manager
from app.performance.task_queue import AnalysisTaskQueue

AnalysisProducer = Callable[[], Any]


class BackgroundAnalysisEngine:
    """Runs independent analysis producers in parallel and caches results."""

    def __init__(
        self,
        max_workers: int = 5,
        cache: Optional[AnalysisCacheManager] = None,
        queue: Optional[AnalysisTaskQueue] = None,
    ) -> None:
        self.max_workers = max(1, int(max_workers))
        self.cache = cache or get_cache_manager()
        self.queue = queue or AnalysisTaskQueue()

    def submit_analysis(
        self,
        name: str,
        producer: AnalysisProducer,
        fingerprint: str = "",
        persist: bool = True,
    ) -> Future[Any]:
        task = self.queue.enqueue(name, fingerprint=fingerprint)
        executor = ThreadPoolExecutor(max_workers=1)

        def run() -> Any:
            self.queue.mark_running(task.task_id)
            try:
                result = self.cache.get_or_compute(name, producer, "analysis", persist, fingerprint)
                self.queue.mark_completed(task.task_id, result=result)
                return result
            except Exception as exc:
                self.queue.mark_failed(task.task_id, exc)
                raise
            finally:
                executor.shutdown(wait=False)

        return executor.submit(run)

    def run_parallel(
        self,
        producers: Mapping[str, AnalysisProducer],
        fingerprints: Optional[Mapping[str, str]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        fingerprints = fingerprints or {}
        results: Dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, max(1, len(producers)))) as executor:
            futures: Dict[Future[Any], str] = {}
            task_ids: Dict[str, str] = {}
            for name, producer in producers.items():
                task = self.queue.enqueue(name, fingerprint=fingerprints.get(name, ""))
                task_ids[name] = task.task_id

                def run_one(name: str = name, producer: AnalysisProducer = producer) -> Any:
                    self.queue.mark_running(task_ids[name])
                    return self.cache.get_or_compute(
                        name,
                        producer,
                        "analysis",
                        persist,
                        fingerprints.get(name, ""),
                    )

                futures[executor.submit(run_one)] = name

            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                    self.queue.mark_completed(task_ids[name], result=results[name])
                except Exception as exc:
                    self.queue.mark_failed(task_ids[name], exc)
                    raise
        return results

    def run_standard_platform(self, jobs: Any, readiness: Any = None) -> Dict[str, Any]:
        from app.ui.framework_intelligence_dashboard import build_framework_intelligence
        from app.ui.impact_intelligence_dashboard import build_impact_intelligence
        from app.ui.migration_intelligence_dashboard import build_migration_intelligence
        from app.ui.upgrade_advisor_dashboard import build_upgrade_advisor

        fp = self.cache.fingerprint(jobs, readiness)
        producers = {
            "impact_analysis": lambda: build_impact_intelligence(jobs, readiness=readiness),
            "framework_analysis": lambda: build_framework_intelligence(jobs),
            "upgrade_advisor": lambda: build_upgrade_advisor(jobs),
            "migration_intelligence": lambda: build_migration_intelligence(jobs, readiness),
        }
        fingerprints = {key: self.cache.fingerprint(key, fp) for key in producers}
        return self.run_parallel(producers, fingerprints)

    def benchmark_parallel_gain(self, producers: Mapping[str, AnalysisProducer]) -> Dict[str, float]:
        start = time.perf_counter()
        sequential = {name: producer() for name, producer in producers.items()}
        sequential_seconds = time.perf_counter() - start
        start = time.perf_counter()
        self.run_parallel({name: (lambda value=value: value) for name, value in sequential.items()}, persist=False)
        parallel_seconds = time.perf_counter() - start
        improvement = 1.0 - (parallel_seconds / sequential_seconds) if sequential_seconds else 0.0
        return {"sequential_seconds": sequential_seconds, "parallel_seconds": parallel_seconds, "improvement": improvement}
