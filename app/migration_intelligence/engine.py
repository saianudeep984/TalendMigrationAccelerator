"""Unified orchestration facade for F10-F12."""
from .complexity_engine import MigrationComplexityEngine
from .critical_path_analyzer import CriticalPathAnalyzer
from .dependency_graph import DependencyGraphEngine
from .effort_estimator import MigrationEffortEstimator
from .strategy_advisor import MigrationStrategyAdvisor
from .wave_planner import MigrationWavePlanner


class MigrationIntelligenceEngine:
    def analyze(self, jobs, readiness=None, lineage_service=None, business_critical_jobs=None):
        graph = DependencyGraphEngine().build(jobs, lineage_service)
        complexity = MigrationComplexityEngine().analyze_project(jobs)
        effort = MigrationEffortEstimator().estimate(complexity, graph)
        strategy = MigrationStrategyAdvisor().recommend(complexity, readiness, effort)
        critical = CriticalPathAnalyzer().analyze(graph, business_critical_jobs)
        waves = MigrationWavePlanner().plan(complexity, graph)
        risks = self._risks(complexity, graph)
        return {"complexity": complexity, "readiness": readiness or {}, "effort": effort,
                "strategy": strategy, "dependency_graph": graph, "critical_paths": critical,
                "migration_waves": waves, "top_risks": risks,
                "executive_summary": self._summary(complexity, effort, strategy, waves, risks)}

    @staticmethod
    def _risks(complexity, graph):
        rows = []
        for job in complexity.get("jobs", []):
            for factor in ("unsupported_components", "custom_java", "dependencies"):
                count = job.get("factors", {}).get(factor, 0)
                if count: rows.append({"job_name": job["job_name"], "risk": factor, "count": count,
                                       "severity": "HIGH" if factor == "unsupported_components" else "MEDIUM"})
        return sorted(rows, key=lambda r: (r["severity"] != "HIGH", -r["count"]))[:10]

    @staticmethod
    def _summary(complexity, effort, strategy, waves, risks):
        return (f"{complexity['job_count']} jobs are assessed at {complexity['complexity']} complexity. "
                f"Estimated effort is {effort['estimated_hours']} hours with a team of {effort['recommended_team_size']}. "
                f"Recommended strategy: {strategy['strategy']}. The plan contains {len(waves['waves'])} waves "
                f"and {len(risks)} prioritized risks.")
