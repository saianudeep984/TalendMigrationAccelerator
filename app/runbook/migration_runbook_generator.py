from __future__ import annotations

import json
from typing import Any, Mapping

from app.migration_intelligence.engine import MigrationIntelligenceEngine
from app.reports.intelligence_exports import export_markdown_report
from app.upgrade_advisor.recommendation_engine import UpgradeRecommendationEngine
from .checklist_engine import MigrationChecklistEngine
from .technical_runbook import TechnicalMigrationRunbook
from .executive_runbook import ExecutiveMigrationRunbook


class MigrationRunbookGenerator:
    def generate(self, jobs, upgrade=None, migration_intelligence=None):
        jobs = list(jobs or [])
        upgrade = upgrade or UpgradeRecommendationEngine().recommend(jobs)
        mi = migration_intelligence or MigrationIntelligenceEngine().analyze(jobs, upgrade.get("readiness"))
        checklist = MigrationChecklistEngine().generate(upgrade)
        technical = TechnicalMigrationRunbook().generate(jobs, upgrade)
        executive = ExecutiveMigrationRunbook().generate(upgrade)
        return {
            "migration_overview": {
                "jobs": len(jobs),
                "recommendation": upgrade["recommendation"]["decision"],
                "readiness": upgrade["readiness"]["upgrade_readiness_percent"],
            },
            "migration_phases": ["Assess", "Fix", "Migrate", "Validate", "Cutover", "Operate"],
            "migration_waves": mi.get("migration_waves", upgrade.get("effort_estimate", {}).get("migration_waves", {})),
            "dependencies": mi.get("dependency_graph", {}),
            "validation_steps": checklist["validation"],
            "rollback_plan": checklist["rollback"],
            "cutover_plan": checklist["go_live"],
            "post_migration_validation": ["Monitor runtime", "Validate SLA", "Close defects", "Handover"],
            "technical_runbook": technical,
            "executive_runbook": executive,
            "checklists": checklist,
            "risks": upgrade.get("breaking_changes", {}).get("findings", []),
        }

    def export(self, runbook: Mapping[str, Any], fmt="json"):
        fmt = (fmt or "json").lower()
        if fmt == "json":
            return json.dumps(runbook, indent=2, default=str)
        md = self.to_markdown(runbook)
        if fmt == "html":
            return export_markdown_report(runbook, md, "Migration Runbook", "html").decode("utf-8")
        if fmt in {"pdf", "docx"}:
            return export_markdown_report(runbook, md, "Migration Runbook", fmt)
        return md

    @staticmethod
    def to_markdown(runbook):
        overview = runbook.get("migration_overview", {})
        executive = runbook.get("executive_runbook", {})
        waves = runbook.get("migration_waves", {}).get("waves", [])
        technical = runbook.get("technical_runbook", {}).get("job_by_job_activities", [])
        lines = [
            "# Migration Runbook",
            "",
            "## Migration Overview",
            f"- Jobs: {overview.get('jobs')}",
            f"- Recommendation: {overview.get('recommendation')}",
            f"- Readiness: {overview.get('readiness')}%",
            "",
            "## Executive Migration Runbook",
            f"- Timeline: {executive.get('timeline')}",
            f"- Strategy: {executive.get('migration_strategy')}",
            f"- Cost Estimate: {executive.get('cost_estimate')}",
            "",
            "## Milestones",
        ]
        lines += [f"- {x}" for x in executive.get("milestones", [])]
        lines += ["", "## Migration Phases"] + [f"- {x}" for x in runbook.get("migration_phases", [])]
        lines += ["", "## Migration Waves"]
        lines += [f"- {w.get('name')}: {', '.join(w.get('jobs', []))}" for w in waves] or ["- Wave plan pending"]
        lines += ["", "## Technical Migration Runbook"]
        for job in technical:
            lines.append(f"- {job.get('job_name')}: {len(job.get('component_fixes', []))} component fixes")
        lines += ["", "## Validation Checklist"] + [f"- {x}" for x in runbook.get("validation_steps", [])]
        lines += ["", "## Cutover Plan"] + [f"- {x}" for x in runbook.get("cutover_plan", [])]
        lines += ["", "## Rollback Plan"] + [f"- {x}" for x in runbook.get("rollback_plan", [])]
        lines += ["", "## Post-Migration Validation"] + [f"- {x}" for x in runbook.get("post_migration_validation", [])]
        return "\n".join(lines)
