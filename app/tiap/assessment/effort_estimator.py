from typing import Any, Dict, Sequence

from app.tiap.assessment.complexity_analyzer import ComplexityAnalyzer


class EffortEstimator:
    def estimate(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None) -> Dict[str, Any]:
        complexity = ComplexityAnalyzer().analyze(all_jobs, repository_path)
        hours = 0.0
        for job in all_jobs:
            score = job.get("complexity", {}).get("score", 0)
            hours += 4 + min(32, score / 8)
            hours += len(job.get("dependencies", {}).get("child_jobs", [])) * 2
        person_days = round(hours / 8, 1)
        person_weeks = round(person_days / 5, 1)
        return {
            "estimated_hours": round(hours, 1),
            "person_days": person_days,
            "person_weeks": person_weeks,
            "sizing_category": complexity["sizing_category"],
            "assumptions": [
                "One person day equals 8 engineering hours.",
                "Estimates include analysis, remediation, validation, and packaging effort.",
            ],
        }
