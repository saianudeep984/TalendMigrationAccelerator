from __future__ import annotations


class ManualRemediationAnalyzer:
    def analyze(self, breaking=None, deprecated=None, autofix=None):
        auto_ids = {str(x.get("component") or x.get("asset") or x.get("id")) for x in (autofix or {}).get("auto_fixable_issues", [])}
        items = []
        for f in (breaking or {}).get("findings", []):
            asset = f.get("affected_assets", [""])[0]
            if asset and asset not in auto_ids:
                items.append({"asset": asset, "required_skills": ["Talend", "Java", "ETL Architecture"], "estimated_effort_hours": 8 if f.get("severity") == "CRITICAL" else 4,
                              "risk_level": f.get("severity", "MEDIUM"), "remediation_steps": [f.get("upgrade_guidance", "Refactor asset"), "Unit test", "Regression validate"]})
        for f in (deprecated or {}).get("findings", []):
            if not f.get("auto_fix_available"):
                items.append({"asset": f["component"], "required_skills": ["Talend"], "estimated_effort_hours": f.get("estimated_effort_hours", 4),
                              "risk_level": f.get("risk", "MEDIUM"), "remediation_steps": [f.get("migration_guidance", "Replace component"), "Validate mappings"]})
        return {"manual_fix_inventory": items, "total_manual_hours": sum(i["estimated_effort_hours"] for i in items)}
