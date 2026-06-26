from collections import defaultdict
from typing import Any, Dict, Sequence

from app.tiap.models.repository import component_parameters, iter_job_data


class ContextProfiler:
    ENV_NAMES = ("dev", "qa", "test", "uat", "prod", "stage", "stg", "sit")

    def profile(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        usage = defaultdict(lambda: {"jobs": set(), "values": set()})
        job_contexts = defaultdict(set)

        for data in iter_job_data(all_jobs):
            job_name = data.get("job_name", "Unknown")
            for ctx in data.get("contexts", []):
                if isinstance(ctx, dict) and ctx.get("name"):
                    name = str(ctx["name"])
                    usage[name]["jobs"].add(job_name)
                    usage[name]["values"].add(str(ctx.get("value", "")))
                    job_contexts[job_name].add(name)
            for component in data.get("components", []):
                if not isinstance(component, dict):
                    continue
                for value in component_parameters(component).values():
                    if "context." not in str(value):
                        continue
                    import re
                    for name in re.findall(r"context\.([A-Za-z_][A-Za-z0-9_]*)", str(value)):
                        usage[name]["jobs"].add(job_name)
                        job_contexts[job_name].add(name)

        duplicates = sorted(name for name, item in usage.items() if len(item["values"] - {""}) > 1)
        shared = sorted(name for name, item in usage.items() if len(item["jobs"]) > 1)
        environment = sorted(name for name in usage if any(token in name.lower() for token in self.ENV_NAMES))
        conflicts = [{"context": name, "values": sorted(usage[name]["values"] - {""})} for name in duplicates]
        opportunities = [
            {"context": name, "jobs": sorted(usage[name]["jobs"]), "recommendation": "Consolidate shared context definition"}
            for name in shared
        ]
        score = min(100, len(usage) * 2 + len(duplicates) * 10 + len(shared) * 3)

        return {
            "repository_context_matrix": {
                job: sorted(contexts) for job, contexts in sorted(job_contexts.items())
            },
            "duplicate_contexts": duplicates,
            "shared_contexts": shared,
            "unused_contexts": [],
            "environment_contexts": environment,
            "context_conflicts": conflicts,
            "context_consolidation_opportunities": opportunities,
            "context_complexity_score": score,
        }


def profile_contexts(all_jobs):
    return ContextProfiler().profile(all_jobs)
