from collections import defaultdict
from typing import Any, Dict, Sequence

from app.tiap.models.repository import component_parameters, iter_job_data


class JobletProfiler:
    def profile(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        usage = defaultdict(set)
        dependencies = defaultdict(set)

        for data in iter_job_data(all_jobs):
            job_name = data.get("job_name", "Unknown")
            for component in data.get("components", []):
                if not isinstance(component, dict):
                    continue
                ctype = component.get("component_type", "")
                if ctype.lower().startswith("tjoblet") or ctype == "tJoblet":
                    params = component_parameters(component)
                    joblet = params.get("JOBLET") or params.get("PROCESS") or component.get("unique_name") or ctype
                    usage[joblet].add(job_name)
                    dependencies[job_name].add(joblet)

        rows = []
        for joblet, jobs in usage.items():
            impact = min(100, len(jobs) * 20)
            rows.append({
                "joblet": joblet,
                "jobs_using_it": sorted(jobs),
                "impact": impact,
                "migration_risk": "HIGH" if impact >= 70 else "MEDIUM" if impact >= 35 else "LOW",
            })
        rows.sort(key=lambda row: (-row["impact"], row["joblet"]))
        return {
            "joblet_usage_matrix": rows,
            "joblet_dependency_matrix": {job: sorted(joblets) for job, joblets in sorted(dependencies.items())},
            "joblet_impact_scores": {row["joblet"]: row["impact"] for row in rows},
        }


def profile_joblets(all_jobs):
    return JobletProfiler().profile(all_jobs)
