import os
from typing import Any, Dict, Sequence

from app.tiap.models.repository import (
    build_adjacency_from_jobs,
    inventory_reference_sets,
    iter_job_data,
    normalize_name,
    scan_repository_files,
)


class OrphanDetector:
    def detect(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None) -> Dict[str, Any]:
        adjacency = build_adjacency_from_jobs(all_jobs)
        known_jobs = {normalize_name(data.get("job_name")) for data in iter_job_data(all_jobs)}
        child_jobs = {child for children in adjacency.values() for child in children}
        parent_jobs = {parent for parent, children in adjacency.items() if children}
        refs = inventory_reference_sets(all_jobs)
        files = scan_repository_files(repository_path) if repository_path else {}

        joblets = {normalize_name(os.path.basename(p).replace(".item", "")) for p in files.get("joblets", [])}
        contexts = {normalize_name(os.path.basename(p).replace(".item", "")) for p in files.get("contexts", [])}
        routines = {normalize_name(os.path.basename(p).replace(".item", "")) for p in files.get("routines", [])}
        metadata = {normalize_name(os.path.basename(p).replace(".item", "")) for p in files.get("metadata", [])}

        result = {
            "orphan_jobs": sorted(job for job in known_jobs if job not in child_jobs and job not in parent_jobs),
            "orphan_joblets": sorted(joblets - refs["joblets"]),
            "orphan_contexts": sorted(contexts - refs["contexts"]),
            "unused_metadata": sorted(metadata - refs["metadata"]),
            "unused_routines": sorted(routines - refs["routines"]),
        }
        recommendations = []
        labels = {
            "orphan_jobs": "Orphan Job",
            "orphan_joblets": "Orphan Joblet",
            "orphan_contexts": "Unused Context",
            "unused_metadata": "Unused Metadata",
            "unused_routines": "Unused Routine",
        }
        for key, label in labels.items():
            for asset in result[key]:
                recommendations.append({"type": label, "asset": asset, "recommendation": "Delete"})
        result["cleanup_recommendations"] = recommendations
        return result


def detect_orphans(all_jobs, repository_path=None):
    return OrphanDetector().detect(all_jobs, repository_path)
