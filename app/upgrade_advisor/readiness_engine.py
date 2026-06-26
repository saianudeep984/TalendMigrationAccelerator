from __future__ import annotations
from app.analyzers.migration_readiness_score import calculate_migration_readiness_score


class UpgradeReadinessEngine:
    def score(self, jobs, compatibility=None, autofix=None, remediation=None):
        readiness = calculate_migration_readiness_score(jobs, {}, []).__dict__
        compat = max(0, 100 - sum((compatibility or {}).get("summary", {}).get(k, 0) * w for k, w in {"Warning": 2, "Deprecated": 5, "Unsupported": 12, "Breaking Change": 20}.items()))
        auto = (autofix or {}).get("auto_fix_coverage_percent", 0)
        manual_hours = (remediation or {}).get("total_manual_hours", 0)
        manual = max(0, 100 - manual_hours)
        base = float(readiness.get("overall_score", readiness.get("score", 70)) or 70)
        overall = round(base * .35 + compat * .3 + auto * .2 + manual * .15, 1)
        return {"upgrade_readiness_percent": overall, "compatibility_readiness": compat, "auto_fix_readiness": auto,
                "manual_remediation_readiness": manual, "base_readiness": readiness}
