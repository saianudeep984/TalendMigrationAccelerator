"""
Migration API

Lightweight internal service layer exposing structured migration data
(e.g. replacement recommendations) to the UI and other consumers.
"""

from typing import Any, Dict, List, Sequence

from app.tiap.profiling.component_profiler import ComponentProfiler
from app.analyzers.unsupported_components_analyzer import UnsupportedComponentsAnalyzer
from app.tiap.migration_assessment.migration_assessment import get_upgrade_path


def get_replacement_recommendations(all_jobs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return a flat list of replacement recommendations for deprecated
    components found across all_jobs.

    Each item: {component, replacementComponent, autoFixable, risk, rationale}
    """
    profiler = ComponentProfiler()
    profile = profiler.profile(all_jobs)
    recommendations = []
    for row in profile.get("deprecated_components", []):
        rec = profiler._replacement_recommendation(row["component"], row["classification"])
        recommendations.append(rec.to_dict())
    return recommendations


def get_remediation_recommendations(all_jobs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return a flat list of remediation actions for unsupported components
    found across all_jobs.

    Each item: {component, category, action, replacementComponent,
                autoFixable, effortHours, risk}
    """
    report = UnsupportedComponentsAnalyzer().analyze(all_jobs)
    return report.get("remediation_actions", [])


def get_upgrade_path_result(job_data: Dict[str, Any], source_version: str = None, target_version: str = "Talend 8") -> Dict[str, Any]:
    """
    Return the UpgradePathResult (as dict) for a single job/repository entry,
    exposing sourceVersion, targetVersions, compatibilityStatus, migrationPath,
    componentFindings, warnings, and blockers to the UI / API consumers.
    """
    return get_upgrade_path(job_data, source_version, target_version)


def get_upgrade_path_results(all_jobs: Sequence[Dict[str, Any]], source_version: str = None, target_version: str = "Talend 8") -> List[Dict[str, Any]]:
    """Return a list of UpgradePathResult dicts, one per job in all_jobs."""
    results = []
    for job in all_jobs:
        job_data = job.get("job_data", job) if isinstance(job, dict) else job
        results.append(get_upgrade_path_result(job_data, source_version, target_version))
    return results
