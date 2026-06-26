from typing import Any, Dict, List


class TrendAnalyzer:
    def analyze(self, current_metrics: Dict[str, Any], history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        history = history or []
        trends = {}
        for key in ("migration_readiness", "cloud_readiness", "testing_readiness", "technical_debt", "pii_risk"):
            previous = history[-1].get(key) if history else None
            current = current_metrics.get(key)
            delta = None if previous is None or current is None else current - previous
            trends[key] = {"current": current, "previous": previous, "delta": delta}
        return {"trend_points": history + [current_metrics], "trends": trends}
