from typing import Any, Dict, Sequence


class PortfolioAnalyzer:
    def analyze(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        buckets = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        cloud = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for job in all_jobs:
            complexity = job.get("complexity", {}).get("complexity") or job.get("estimation", {}).get("complexity", "LOW")
            buckets[complexity if complexity in buckets else "LOW"] += 1
            readiness = job.get("cloud_readiness", {}).get("readiness", "LOW")
            cloud[readiness if readiness in cloud else "LOW"] += 1
        return {
            "portfolio_view": {
                "jobs_by_complexity": buckets,
                "jobs_by_cloud_readiness": cloud,
            },
            "migration_progress": {
                "assessed": len(all_jobs),
                "ready": cloud["HIGH"],
                "needs_remediation": cloud["LOW"] + cloud["MEDIUM"],
            },
        }
