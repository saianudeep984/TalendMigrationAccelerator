from typing import Dict, Any
from app.analyzers.complexity_analyzer import THRESHOLDS as _THRESHOLDS


class MigrationEstimator:

    def estimate(
        self,
        job_data: Dict[str, Any],
        dependencies: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Estimate migration complexity, effort, and score.

        Args:
            job_data (Dict): Parsed Talend job data
            dependencies (Dict): Dependency analysis data

        Returns:
            Dict: Migration estimation details
        """

        components = job_data.get("components", [])
        component_count = len(components)

        # Build a set of component TYPE strings for fast O(1) membership checks.
        # components are dicts: {"component_type": str, ...}
        comp_types = {
            c.get("component_type", "") if isinstance(c, dict) else str(c)
            for c in components
        }

        score = 0

        # Component-volume scoring
        if component_count < 10:
            score += 10
        elif component_count < 30:
            score += 30
        else:
            score += 60

        # High-complexity component penalties (check type strings, not raw dicts)
        if "tJava" in comp_types or "tJavaRow" in comp_types or "tJavaFlex" in comp_types:
            score += 30

        if "tSystem" in comp_types:
            score += 40

        if "tLibraryLoad" in comp_types:
            score += 25

        if "tBeanShell" in comp_types:
            score += 20

        # Child jobs penalty
        child_jobs = dependencies.get("child_jobs", [])
        score += len(child_jobs) * 10

        # Complexity classification
        if score < _THRESHOLDS["LOW"]:
            complexity = "LOW"
            hours = 4

        elif score < _THRESHOLDS["MEDIUM"]:
            complexity = "MEDIUM"
            hours = 16

        elif score < _THRESHOLDS["HIGH"]:
            complexity = "HIGH"
            hours = 40

        else:
            complexity = "CRITICAL"
            hours = 80

        return {
            "complexity": complexity,
            "estimated_hours": hours,
            "estimated_days": round(hours / 8, 1),
            "migration_score": score,
            "component_count": component_count,
            "child_job_count": len(child_jobs)
        }
