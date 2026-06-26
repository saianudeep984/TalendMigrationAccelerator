from __future__ import annotations


class FrameworkMaturityAnalyzer:
    def score(self, inventory):
        coverage = inventory.get("framework_coverage", 0)
        usage = inventory.get("framework_usage", {})
        scores = {
            "reusability": min(100, coverage + usage.get("reusable_joblet_framework", 0) * 5),
            "maintainability": min(100, coverage + usage.get("context_framework", 0) * 5),
            "scalability": min(100, coverage + usage.get("batch_framework", 0) * 5),
            "operational_readiness": min(100, coverage + usage.get("error_handling_framework", 0) * 5),
            "monitoring_readiness": min(100, coverage + usage.get("logging_framework", 0) * 5),
            "upgrade_readiness": min(100, coverage + usage.get("metadata_framework", 0) * 3),
        }
        scores["framework_maturity_score"] = round(sum(scores.values()) / len(scores), 1)
        return scores
