from typing import Any, Dict, Sequence

from app.tiap.profiling.component_profiler import ComponentProfiler
from app.tiap.profiling.context_profiler import ContextProfiler
from app.tiap.profiling.joblet_profiler import JobletProfiler
from app.tiap.profiling.orphan_detector import OrphanDetector
from app.tiap.profiling.routine_profiler import RoutineProfiler


class RepositoryScoring:
    def score(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None) -> Dict[str, Any]:
        component = ComponentProfiler().profile(all_jobs)
        context = ContextProfiler().profile(all_jobs)
        routine = RoutineProfiler().profile(all_jobs, repository_path)
        joblet = JobletProfiler().profile(all_jobs)
        orphan = OrphanDetector().detect(all_jobs, repository_path)

        total_jobs = max(1, len(all_jobs))
        avg_complexity = sum(j.get("complexity", {}).get("score", 0) for j in all_jobs) / total_jobs
        risk_components = (
            len(component["deprecated_components"])
            + len(component["custom_components"]) * 2
            + len(component["unknown_components"])
        )
        high_routines = sum(1 for row in routine["routine_usage"] if row["risk"] == "HIGH")
        orphan_count = sum(len(orphan[key]) for key in ("orphan_jobs", "orphan_joblets", "orphan_contexts", "unused_metadata", "unused_routines"))

        repository_complexity = min(100, int(avg_complexity * 0.5 + risk_components * 5 + context["context_complexity_score"] * 0.2))
        cloud_readiness = max(0, 100 - min(100, risk_components * 7 + high_routines * 12))
        documentation_readiness = max(0, 100 - min(70, orphan_count * 5))
        testing_readiness = max(0, 100 - min(80, repository_complexity * 0.4 + len(joblet["joblet_usage_matrix"]) * 5))
        migration_readiness = int(
            cloud_readiness * 0.35
            + documentation_readiness * 0.2
            + testing_readiness * 0.2
            + (100 - repository_complexity) * 0.25
        )

        return {
            "repository_complexity_score": repository_complexity,
            "migration_readiness_score": migration_readiness,
            "cloud_readiness_score": int(cloud_readiness),
            "documentation_readiness_score": int(documentation_readiness),
            "testing_readiness_score": int(testing_readiness),
            "weights": {
                "cloud_readiness": 0.35,
                "documentation_readiness": 0.20,
                "testing_readiness": 0.20,
                "inverse_complexity": 0.25,
            },
        }


def score_repository(all_jobs, repository_path=None):
    return RepositoryScoring().score(all_jobs, repository_path)
