import os
from typing import Any, Dict, Sequence

from app.tiap.governance.data_classification import DataClassification
from app.tiap.governance.pii_scanner import PIIScanner
from app.tiap.governance.risk_profiler import GovernanceRiskProfiler
from app.tiap.models.repository import write_json


class ComplianceAssessor:
    def assess(self, all_jobs: Sequence[Dict[str, Any]], output_dir: str = None) -> Dict[str, Any]:
        pii = PIIScanner().scan(all_jobs)
        classification = DataClassification().classify(pii)
        risk = GovernanceRiskProfiler().profile(pii, classification)
        pii_types = set(classification.get("detected_pii_types", []))
        report = {
            "pii_detection": pii,
            "data_classification": classification,
            "risk_profile": risk,
            "compliance_report": {
                "GDPR": "Applicable" if pii_types else "Low applicability",
                "CCPA": "Applicable" if pii_types else "Low applicability",
                "HIPAA": "Review required" if {"SSN", "Phone", "Email"} & pii_types else "Low applicability",
                "PCI": "Applicable" if "Credit Card" in pii_types else "Low applicability",
            },
            "controls": [
                "Do not send actual data rows to LLMs.",
                "Mask restricted fields in non-production environments.",
                "Validate retention and access policy before migration.",
            ],
        }
        if output_dir:
            write_json(os.path.join(output_dir, "governance_report.json"), report)
        return report
