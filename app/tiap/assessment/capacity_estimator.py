from typing import Any, Dict, Sequence


class CapacityEstimator:
    def estimate(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        jobs = len(all_jobs)
        components = sum(len(job.get("job_data", {}).get("components", [])) for job in all_jobs)
        return {
            "cpu_cores": max(2, min(64, int(2 + jobs / 50 + components / 1000))),
            "memory_gb": max(4, min(256, int(4 + jobs / 20 + components / 250))),
            "storage_gb": max(20, int(20 + jobs * 0.5 + components * 0.05)),
            "basis": {"jobs": jobs, "components": components},
        }
