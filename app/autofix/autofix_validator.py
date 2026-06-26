"""Validation framework that prevents invalid auto-fix recommendations."""
from __future__ import annotations

from typing import Any, Dict, List

from app.config.component_rules import TALEND8_KNOWN_COMPONENTS


class AutoFixValidationFramework:
    def validate(self, autofix: Dict[str, Any], rule_repository=None) -> Dict[str, Any]:
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        for rec in autofix.get("recommendations", []) or []:
            after = rec.get("after_state", {})
            replacement = after.get("component")
            if rec.get("type") == "component_migration":
                if not replacement:
                    errors.append({"id": rec.get("id"), "error": "Missing replacement component."})
                elif replacement not in TALEND8_KNOWN_COMPONENTS and "T8 OK" not in replacement and "/" not in replacement and "equivalent" not in replacement:
                    warnings.append({"id": rec.get("id"), "warning": f"Replacement '{replacement}' requires manual compatibility confirmation."})
                if rec.get("auto_fixable") and rec.get("risk") in {"HIGH", "CRITICAL"}:
                    warnings.append({"id": rec.get("id"), "warning": "High-risk automatic fix requires approval gate."})
            if not rec.get("remediation_steps"):
                errors.append({"id": rec.get("id"), "error": "Missing remediation steps."})
        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "validated_recommendations": len(autofix.get("recommendations", []) or []),
        }

