"""Generate before/after auto-fix remediation instructions."""
from __future__ import annotations

from typing import Any, Dict, List

from app.autofix.rule_engine import AutoFixRuleEngine


class AutoFixGenerator:
    def __init__(self, rule_engine: AutoFixRuleEngine = None):
        self.rule_engine = rule_engine or AutoFixRuleEngine()

    def generate(self, jobs, anti_patterns: Dict[str, Any] = None) -> Dict[str, Any]:
        component_result = self.rule_engine.analyze_components(jobs)
        recommendations: List[Dict[str, Any]] = []
        for f in component_result["findings"]:
            recommendations.append({
                "id": f"{f['job_name']}::{f['component']}::{f['replacement']}",
                "job_name": f["job_name"],
                "type": "component_migration",
                "risk": f["risk"],
                "auto_fixable": f["auto_fix"],
                "before_state": {"component": f["component"], "version": "Talend 7.x"},
                "after_state": {"component": f["replacement"], "version": "Talend 8.x"},
                "remediation_steps": [
                    f"Create backup of {f['job_name']}.",
                    f"Replace {f['component']} with {f['replacement']}.",
                    "Map existing schema, connection, and context parameters.",
                    "Run compile, unit, and regression validation.",
                ],
                "migration_instructions": f["recommendation"],
            })
        for f in (anti_patterns or {}).get("findings", []) or []:
            recommendations.append({
                "id": f"architecture::{f.get('type')}::{f.get('asset')}",
                "job_name": f.get("asset", "repository"),
                "type": f.get("type"),
                "risk": f.get("severity", "MEDIUM"),
                "auto_fixable": f.get("type") in {"hardcoded_paths"},
                "before_state": {"issue": f.get("message")},
                "after_state": {"target": self._target(f.get("type"))},
                "remediation_steps": self._steps(f.get("type")),
                "migration_instructions": f.get("message", ""),
            })
        return {"recommendations": recommendations, "component_rules": component_result, "summary": {
            "total": len(recommendations),
            "auto_fixable": sum(r["auto_fixable"] for r in recommendations),
            "manual_review": sum(not r["auto_fixable"] for r in recommendations),
        }}

    @staticmethod
    def _target(kind):
        return {
            "hardcoded_paths": "Context/environment-managed path",
            "hardcoded_credentials": "Vault/secret/context password parameter",
            "missing_error_handling": "Standard tLogCatcher/tDie/tWarn pattern",
            "excessive_inline_java": "Routine/native component implementation",
            "duplicate_job_logic": "Reusable joblet/subjob",
            "excessive_tmap_complexity": "Split and documented mapping design",
            "deep_dependency_chains": "Flattened migration wave dependency",
        }.get(kind, "Talend enterprise standard")

    @staticmethod
    def _steps(kind):
        return {
            "hardcoded_paths": ["Create context variable.", "Replace literal path.", "Validate per environment."],
            "hardcoded_credentials": ["Remove literal secret.", "Create protected context/secret reference.", "Rotate exposed value."],
            "missing_error_handling": ["Add central catcher.", "Route failures to logging.", "Add failure assertions."],
            "excessive_inline_java": ["Extract reusable code.", "Replace simple logic with native components.", "Regression test."],
            "duplicate_job_logic": ["Compare duplicate flows.", "Extract common joblet.", "Replace duplicate subflows."],
            "excessive_tmap_complexity": ["Split map.", "Name intermediate schemas.", "Validate lookup semantics."],
            "deep_dependency_chains": ["Review orchestration.", "Create migration waves.", "Reduce synchronous child chains."],
        }.get(kind, ["Review finding.", "Apply approved remediation.", "Validate migration."])

