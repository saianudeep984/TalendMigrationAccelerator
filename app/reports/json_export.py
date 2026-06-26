"""
JSON export for complete assessment reports.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Sequence

from app.tiap.documentation.export_utils import resolve_source_version as _resolve_source_version


def write_complete_assessment_json(
    path: str,
    sections: Dict[str, str],
    all_jobs: Sequence[Dict[str, Any]] = (),
    repository_path: str | None = None,
    repository_overview: Dict[str, Any] | None = None,
) -> str:
    """Write a structured JSON export with repositoryOverview and upgradePath keys."""
    total_jobs = len(all_jobs)
    source_version = _resolve_source_version(all_jobs, repository_path)

    repo_overview = repository_overview or {
        "totalJobs": total_jobs,
        "sourceVersion": source_version,
        "targetVersion": "Talend 8",
    }
    if "totalJobs" not in repo_overview:
        repo_overview["totalJobs"] = total_jobs

    upgrade_jobs = []
    for job in all_jobs:
        jd = job.get("job_data", {})
        complexity = job.get("complexity", {})
        level = complexity.get("level") if isinstance(complexity, dict) else "UNKNOWN"
        upgrade_jobs.append({
            "jobName": jd.get("job_name", "Unknown"),
            "sourceVersion": jd.get("source_version", source_version),
            "targetVersion": "Talend 8",
            "components": len(jd.get("components", [])),
            "complexity": level or "UNKNOWN",
        })

    if all_jobs:
        upgrade_path: Dict[str, Any] = {
            "available": True,
            "sourceVersion": source_version,
            "targetVersion": "Talend 8",
            "jobs": upgrade_jobs,
        }
    else:
        upgrade_path = {
            "available": False,
            "sourceVersion": source_version,
            "targetVersion": "Talend 8",
            "jobs": [],
        }

    payload = {
        "repositoryOverview": repo_overview,
        "upgradePath": upgrade_path,
        "sections": {k: v for k, v in sections.items()},
    }

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)

    return path
