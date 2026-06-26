from __future__ import annotations
from app.migration_intelligence.engine import MigrationIntelligenceEngine


class UpgradeImpactAssessmentEngine:
    def assess(self, jobs, compatibility=None, breaking=None, deprecated=None, migration_intelligence=None):
        migration_intelligence = migration_intelligence or MigrationIntelligenceEngine().analyze(jobs, {})
        compatibility = compatibility or {}
        breaking = breaking or {}
        deprecated = deprecated or {}
        total = max(1, len(compatibility.get("findings", [])))
        bad = sum(compatibility.get("summary", {}).get(k, 0) for k in ("Warning", "Deprecated", "Unsupported", "Breaking Change"))
        compat_score = round(max(0, 100 - bad / total * 100), 1)
        risk_score = min(100, round((breaking.get("summary", {}).get("critical", 0) * 20) + deprecated.get("summary", {}).get("total", 0) * 6 + len(migration_intelligence.get("top_risks", [])) * 3, 1))
        impact_score = round((100 - compat_score) * .55 + risk_score * .45, 1)
        level = "LOW" if impact_score < 25 else "MEDIUM" if impact_score < 50 else "HIGH" if impact_score < 75 else "CRITICAL"
        return {"upgrade_impact_score": impact_score, "compatibility_score": compat_score, "upgrade_risk_score": risk_score, "classification": level}
