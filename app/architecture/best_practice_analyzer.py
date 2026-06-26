"""Talend enterprise and migration best-practice compliance analysis."""
from __future__ import annotations

from typing import Any, Dict, List


class BestPracticeAnalyzer:
    PRACTICES = (
        ("externalized_configuration", "No hardcoded paths or credentials", ("hardcoded_paths", "hardcoded_credentials")),
        ("standard_error_handling", "Every job has explicit error handling", ("missing_error_handling",)),
        ("low_custom_code", "Inline Java/script is minimized", ("excessive_inline_java",)),
        ("modular_reuse", "Shared logic is implemented through joblets/reusable assets", ("duplicate_job_logic",)),
        ("manageable_mapping", "tMap complexity remains reviewable", ("excessive_tmap_complexity",)),
        ("shallow_dependencies", "Dependency chains remain operable", ("deep_dependency_chains",)),
    )

    def analyze(self, anti_patterns: Dict[str, Any], scorecard: Dict[str, Any] = None) -> Dict[str, Any]:
        counts = anti_patterns.get("summary", {}) or {}
        rows: List[Dict[str, Any]] = []
        for key, label, related in self.PRACTICES:
            misses = sum(counts.get(r, 0) for r in related)
            score = max(0, 100 - misses * 20)
            rows.append({
                "practice": key,
                "description": label,
                "score": score,
                "status": "COMPLIANT" if score >= 80 else "PARTIAL" if score >= 50 else "NON_COMPLIANT",
                "findings": misses,
                "remediation": self._remediation(key),
            })
        compliance = int(sum(r["score"] for r in rows) / len(rows)) if rows else 100
        return {
            "compliance_score": compliance,
            "compliance_band": "HIGH" if compliance >= 80 else "MEDIUM" if compliance >= 60 else "LOW",
            "standards": rows,
            "remediation_plan": [r for r in rows if r["status"] != "COMPLIANT"],
        }

    @staticmethod
    def _remediation(key: str) -> str:
        return {
            "externalized_configuration": "Move literals to contexts, environment variables, or repository metadata.",
            "standard_error_handling": "Add tLogCatcher/tDie/tWarn paths and central logging.",
            "low_custom_code": "Move repeated Java into routines or native Talend components.",
            "modular_reuse": "Extract repeated subflows into joblets.",
            "manageable_mapping": "Split large maps and document lookup/transform intent.",
            "shallow_dependencies": "Flatten orchestration chains and introduce wave boundaries.",
        }.get(key, "Apply Talend enterprise migration standards.")

