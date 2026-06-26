from typing import Any, Dict


class GovernanceRiskProfiler:
    def profile(self, pii_report: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
        score = pii_report.get("pii_risk_score", 0)
        if classification.get("classification") == "Restricted":
            score = min(100, score + 25)
        return {
            "governance_risk_score": score,
            "governance_risk": "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW",
            "risk_drivers": classification.get("detected_pii_types", []),
        }
