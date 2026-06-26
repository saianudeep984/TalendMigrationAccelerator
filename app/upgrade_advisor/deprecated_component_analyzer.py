from __future__ import annotations
from app.config.component_rules import DEPRECATED_COMPONENT_MAP
from .upgrade_inventory import components, ctype, job_data


class UpgradeDeprecatedComponentAnalyzer:
    def analyze(self, jobs):
        findings = []
        for j in jobs or []:
            name = job_data(j).get("job_name") or j.get("job_name")
            for c in components(j):
                t = ctype(c)
                if t in DEPRECATED_COMPONENT_MAP:
                    rule = DEPRECATED_COMPONENT_MAP[t]
                    findings.append({"job_name": name, "component": t, "replacement_component": rule["replacement"],
                                     "migration_guidance": f"Replace {t} with {rule['replacement']}.",
                                     "estimated_effort_hours": 2 if rule.get("auto_fix") else 6,
                                     "auto_fix_available": bool(rule.get("auto_fix")), "risk": rule.get("risk", "MEDIUM")})
        return {"summary": {"total": len(findings), "auto_fixable": sum(f["auto_fix_available"] for f in findings)}, "findings": findings}
