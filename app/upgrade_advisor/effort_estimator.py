from __future__ import annotations
from app.migration_intelligence.engine import MigrationIntelligenceEngine
from app.migration_intelligence.wave_planner import MigrationWavePlanner


class UpgradeEffortEstimator:
    def estimate(self, jobs, impact=None, remediation=None, migration_intelligence=None):
        mi = migration_intelligence or MigrationIntelligenceEngine().analyze(jobs, {})
        base = mi.get("effort", {})
        manual = (remediation or {}).get("total_manual_hours", 0)
        impact_score = (impact or {}).get("upgrade_impact_score", 0)
        total = round(float(base.get("estimated_hours", 0) or 0) + manual + impact_score * .5, 1)
        team = max(1, min(8, round(total / 240) + 1 if total else 1))
        graph = mi.get("dependency_graph", {})
        waves = mi.get("migration_waves") or MigrationWavePlanner().plan(mi.get("complexity", {}), graph)
        return {"total_hours": total, "estimated_duration_weeks": round(total / max(1, team * 40), 1),
                "recommended_team_size": team, "resource_plan": {"talend_developers": team, "qa": max(1, team // 2), "architect": 1},
                "migration_waves": waves, "project_estimate": base, "job_level_estimates": base.get("job_breakdown", [])}
