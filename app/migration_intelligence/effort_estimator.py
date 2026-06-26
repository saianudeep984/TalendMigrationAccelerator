"""Dependency-aware migration effort estimation."""
import math


class MigrationEffortEstimator:
    LEVEL_BASE_HOURS = {"LOW": 6, "MEDIUM": 16, "HIGH": 32, "CRITICAL": 64}

    def estimate(self, complexity, graph=None, productivity_hours=30):
        jobs = complexity.get("jobs", []) if isinstance(complexity, dict) else list(complexity or [])
        graph = graph or {"edges": []}
        degrees = {}
        for edge in graph.get("edges", []):
            degrees[edge["source"]] = degrees.get(edge["source"], 0) + 1
            degrees[edge["target"]] = degrees.get(edge["target"], 0) + 1
        breakdown = []
        for job in jobs:
            factors = job.get("factors", {})
            hours = self.LEVEL_BASE_HOURS.get(job.get("complexity", "LOW"), 6)
            hours += factors.get("unsupported_components", 0) * 8
            hours += factors.get("custom_java", 0) * 4
            hours += factors.get("components", 0) * .25
            hours += degrees.get(job.get("job_name"), 0) * 1.5
            hours = round(hours, 1)
            breakdown.append({"job_name": job.get("job_name"), "complexity": job.get("complexity"),
                              "estimated_hours": hours, "build_hours": round(hours * .55, 1),
                              "test_hours": round(hours * .3, 1), "deployment_hours": round(hours * .15, 1)})
        total = round(sum(x["estimated_hours"] for x in breakdown), 1)
        team = 0 if not total else max(1, min(8, math.ceil(total / (productivity_hours * 8))))
        days = round(total / (max(team, 1) * 8), 1) if total else 0
        return {"estimated_hours": total, "estimated_days": days, "estimated_weeks": round(days / 5, 1),
                "recommended_team_size": team, "job_breakdown": breakdown,
                "project_breakdown": {
                    "build_hours": round(sum(x["build_hours"] for x in breakdown), 1),
                    "test_hours": round(sum(x["test_hours"] for x in breakdown), 1),
                    "deployment_hours": round(sum(x["deployment_hours"] for x in breakdown), 1)}}

    estimate_project = estimate


def estimate_migration_effort(complexity, graph=None):
    return MigrationEffortEstimator().estimate(complexity, graph)
