"""Rule repository for Talend migration auto-fix intelligence."""
from __future__ import annotations

from typing import Any, Dict, List

from app.config.component_rules import DEPRECATED_COMPONENT_MAP, TALEND8_KNOWN_COMPONENTS


class MigrationRuleRepository:
    def __init__(self, rules: Dict[str, Dict[str, Any]] = None):
        self.rules = rules or DEPRECATED_COMPONENT_MAP

    def component_rule(self, component_type: str) -> Dict[str, Any] | None:
        rule = self.rules.get(component_type)
        if rule:
            return {"component": component_type, "status": "DEPRECATED", **rule}
        if component_type and component_type not in TALEND8_KNOWN_COMPONENTS:
            return {"component": component_type, "status": "UNKNOWN", "replacement": "Talend 8 supported equivalent", "auto_fix": False, "risk": "HIGH"}
        return None

    def all_rules(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.rules)


class AutoFixRuleEngine:
    def __init__(self, repository: MigrationRuleRepository = None):
        self.repository = repository or MigrationRuleRepository()

    def analyze_components(self, jobs) -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []
        for wrapper in jobs or []:
            data = wrapper.get("job_data", wrapper) if isinstance(wrapper, dict) else {}
            job = data.get("job_name", "Unknown")
            for comp in data.get("components", []) or []:
                ctype = comp.get("component_type", str(comp)) if isinstance(comp, dict) else str(comp)
                rule = self.repository.component_rule(ctype)
                if not rule:
                    continue
                findings.append({
                    "job_name": job,
                    "component": ctype,
                    "replacement": rule.get("replacement"),
                    "status": rule.get("status"),
                    "risk": str(rule.get("risk", "MEDIUM")).upper(),
                    "auto_fix": bool(rule.get("auto_fix")),
                    "recommendation": self.recommend_component_migration(ctype),
                })
        return {
            "findings": findings,
            "summary": {"total": len(findings), "auto_fixable": sum(f["auto_fix"] for f in findings)},
            "upgrade_recommendations": self.talend_7_to_8_recommendations(findings),
        }

    def recommend_component_migration(self, component_type: str) -> str:
        rule = self.repository.component_rule(component_type)
        if not rule:
            return f"{component_type} is compatible with the known Talend 8 component catalog."
        return f"Replace {component_type} with {rule.get('replacement')} and validate schemas, contexts, and runtime behavior."

    @staticmethod
    def talend_7_to_8_recommendations(findings) -> List[Dict[str, Any]]:
        rows = []
        for f in findings:
            rows.append({
                "job_name": f["job_name"],
                "source_version": "Talend 7.x",
                "target_version": "Talend 8.x",
                "component": f["component"],
                "upgrade_action": "automatic_mapping" if f["auto_fix"] else "manual_review",
                "replacement": f["replacement"],
                "risk": f["risk"],
            })
        return rows

