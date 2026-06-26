class ExecutiveMigrationRunbook:
    def generate(self, upgrade=None, portfolio=None):
        effort = (upgrade or {}).get("effort_estimate", {})
        readiness = (upgrade or {}).get("readiness", {})
        return {"timeline": f"{effort.get('estimated_duration_weeks', 0)} weeks", "milestones": ["Assessment", "Remediation", "Migration Waves", "Validation", "Cutover"],
                "risks": (upgrade or {}).get("breaking_changes", {}).get("findings", [])[:10],
                "resource_plan": effort.get("resource_plan", {}), "migration_strategy": (upgrade or {}).get("recommendation", {}).get("decision", "Proceed With Fixes"),
                "cost_estimate": effort.get("total_hours", 0) * 125, "success_criteria": [f"Readiness >= {readiness.get('upgrade_readiness_percent', 0)} baseline", "Zero critical defects", "Rollback tested"]}
