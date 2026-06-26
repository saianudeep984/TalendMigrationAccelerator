import os
from typing import Any, Dict, Sequence

from app.tiap.assessment.capacity_estimator import CapacityEstimator
from app.tiap.assessment.cloud_readiness import CloudReadinessAnalyzer
from app.tiap.assessment.complexity_analyzer import ComplexityAnalyzer
from app.tiap.assessment.effort_estimator import EffortEstimator
from app.tiap.models.repository import write_json
from app.tiap.scoring.repository_scoring import RepositoryScoring


class MigrationReadinessAnalyzer:
    def analyze(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None, output_dir: str = None) -> Dict[str, Any]:
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
