"""
Migration Readiness Scoring Engine
Produces an overall RAG (RED/AMBER/GREEN) rating with dimension breakdown.
"""

from app.readiness.component_compatibility import REMOVED_COMPONENTS
from app.analyzers.cloud_readiness import CloudReadinessAnalyzer  # noqa: F401 (canonical, F2.2/F2.3)

_READINESS_WEIGHT = {"HIGH": 100, "MEDIUM": 60, "LOW": 20}


def _rag(value: int) -> str:
    """Map a 0-100 numeric score to a RED/AMBER/GREEN rating."""
    if value >= 70:
        return "GREEN"
    elif value >= 40:
        return "AMBER"
    else:
        return "RED"


def score_to_rag(score, low=40, high=70) -> str:
    """Convert a numeric score to RED/AMBER/GREEN."""
    try:
        s = int(score)
    except (TypeError, ValueError):
        return "AMBER"
    if s >= high:
        return "GREEN"
    if s >= low:
        return "AMBER"
    return "RED"


def calculate_readiness_score(all_jobs, custom_analysis, deprecated_rows):
    """
    Legacy-shape RAG readiness summary, delegating to the canonical
    MigrationReadinessScoreCalculator (app.analyzers.migration_readiness_score)
    so there is a single scoring implementation (see F2.5).

    Returns:
        {
          overall: str (RED/AMBER/GREEN),
          component_compatibility: str (RED/AMBER/GREEN),
          deprecated_component_risk: str (RED/AMBER/GREEN),
          custom_component_risk: str (RED/AMBER/GREEN),
          cloud_readiness: str (RED/AMBER/GREEN),
          dependency_complexity: str (RED/AMBER/GREEN),
          status: str,
          breakdown: [ {dimension, rag, detail} ]
        }
    """
    from app.analyzers.migration_readiness_score import calculate_migration_readiness_score

    if not all_jobs:
        return {"overall": "RED", "status": "NO DATA"}

    result = calculate_migration_readiness_score(all_jobs, custom_analysis, deprecated_rows)

    by_label = {d["dimension"]: d for d in result.dimensions}
    legacy_keys = [
        ("Component Compatibility", "component_compatibility"),
        ("Deprecated Component Risk", "deprecated_component_risk"),
        ("Custom Component Risk", "custom_component_risk"),
        ("Cloud Readiness", "cloud_readiness"),
        ("Dependency Complexity", "dependency_complexity"),
    ]

    out = {"overall": result.overall_rag, "status": result.status}
    for label, key in legacy_keys:
        out[key] = by_label[label]["rag"]
    out["breakdown"] = [
        {"dimension": label, "rag": by_label[label]["rag"], "detail": by_label[label]["detail"]}
        for label, _ in legacy_keys
    ]
    return out


class Talend8Readiness:
    def evaluate(self, job_data: dict) -> dict:
        blockers = []
        warnings = []

        for component in job_data.get("components", []):
            comp_type = component.get("component_type", "")
            if comp_type in REMOVED_COMPONENTS:
                blockers.append({
                    "component": comp_type,
                    "severity": "CRITICAL",
                    "reason": (
                        f"{comp_type} was removed in Talend 8. "
                        "Must be replaced before migration."
                    )
                })

        if len(blockers) == 0:
            score = 100
            status = "READY"
        elif len(blockers) <= 2:
            score = 50
            status = "NEEDS REMEDIATION"
        else:
            score = 10
            status = "BLOCKED"

        return {
            "job_name": job_data.get("job_name", "Unknown"),
            "blockers": blockers,
            "warnings": warnings,
            "blocker_count": len(blockers),
            "readiness_score": score,
            "status": status,
        }

    def evaluate_repository(self, all_jobs: list) -> dict:
        all_results = []
        total_blockers = 0

        for job in all_jobs:
            result = self.evaluate(job.get("job_data", {}))
            all_results.append(result)
            total_blockers += result["blocker_count"]

        overall_score = 100 if total_blockers == 0 else max(0, 100 - total_blockers * 10)

        return {
            "job_results": all_results,
            "total_blockers": total_blockers,
            "overall_score": overall_score,
            "overall_status": (
                "READY" if overall_score >= 80
                else "PARTIAL" if overall_score >= 40
                else "BLOCKED"
            ),
        }


class MigrationReadiness:
    def evaluate(self, all_jobs):
        high_risk = 0
        cloud_blockers = 0

        for job in all_jobs:
            for risk in job.get("enterprise_risk_report", []):
                if risk.get("risk") in ["HIGH", "CRITICAL"]:
                    high_risk += 1

            if job.get("cloud_readiness", {}).get("readiness") == "LOW":
                cloud_blockers += 1

        score = max(0, 100 - (high_risk * 5 + cloud_blockers * 10))

        if score >= 80:
            status = "READY"
        elif score >= 50:
            status = "PARTIAL"
        else:
            status = "HIGH REMEDIATION REQUIRED"

        return {
            "score": score,
            "status": status,
            "high_risk_components": high_risk,
            "cloud_blockers": cloud_blockers,
        }


class RepositoryScoring:
    def score(self, all_jobs, repository_path: str = None) -> dict:
        from app.tiap.profiling.component_profiler import ComponentProfiler
        from app.tiap.profiling.context_profiler import ContextProfiler
        from app.tiap.profiling.joblet_profiler import JobletProfiler
        from app.tiap.profiling.orphan_detector import OrphanDetector
        from app.tiap.profiling.routine_profiler import RoutineProfiler

        component = ComponentProfiler().profile(all_jobs)
        context = ContextProfiler().profile(all_jobs)
        routine = RoutineProfiler().profile(all_jobs, repository_path)
        joblet = JobletProfiler().profile(all_jobs)
        orphan = OrphanDetector().detect(all_jobs, repository_path)

        total_jobs = max(1, len(all_jobs))
        avg_complexity = sum(j.get("complexity", {}).get("score", 0) for j in all_jobs) / total_jobs
        risk_components = (
            len(component.get("deprecated_components", []))
            + len(component.get("custom_components", [])) * 2
            + len(component.get("unknown_components", []))
        )
        high_routines = sum(1 for row in routine.get("routine_usage", []) if row.get("risk") == "HIGH")
        orphan_count = sum(
            len(orphan.get(key, []))
            for key in ("orphan_jobs", "orphan_joblets", "orphan_contexts", "unused_metadata", "unused_routines")
        )

        repository_complexity = min(
            100,
            int(avg_complexity * 0.5 + risk_components * 5 + context.get("context_complexity_score", 0) * 0.2),
        )
        cloud_readiness = max(0, 100 - min(100, risk_components * 7 + high_routines * 12))
        documentation_readiness = max(0, 100 - min(70, orphan_count * 5))
        testing_readiness = max(
            0,
            100 - min(80, repository_complexity * 0.4 + len(joblet.get("joblet_usage_matrix", [])) * 5),
        )
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


class MigrationReadinessAnalyzer:
    def analyze(self, all_jobs, repository_path: str = None, output_dir: str = None) -> dict:
        import os

        from app.tiap.assessment.capacity_estimator import CapacityEstimator
        from app.tiap.assessment.complexity_analyzer import ComplexityAnalyzer
        from app.tiap.assessment.effort_estimator import EffortEstimator
        from app.tiap.models.repository import write_json

        complexity = ComplexityAnalyzer().analyze(all_jobs, repository_path)
        cloud = CloudReadinessAnalyzer().analyze(all_jobs)
        effort = EffortEstimator().estimate(all_jobs, repository_path)
        capacity = CapacityEstimator().estimate(all_jobs)
        scoring = RepositoryScoring().score(all_jobs, repository_path)
        result = {
            "repository_complexity": complexity,
            "migration_readiness_percent": scoring["migration_readiness_score"],
            "cloud_readiness_percent": cloud["cloud_readiness_score"],
            "complexity_score": complexity["repository_complexity_score"],
            "effort_estimation": effort,
            "capacity_estimation": capacity,
            "migration_sizing_category": complexity["sizing_category"],
            "testing_readiness_percent": scoring["testing_readiness_score"],
            "documentation_readiness_percent": scoring["documentation_readiness_score"],
            "cloud_readiness": cloud,
        }
        if output_dir:
            write_json(os.path.join(output_dir, "migration_assessment.json"), result)
        return result
