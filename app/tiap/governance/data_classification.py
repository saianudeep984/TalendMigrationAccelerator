from typing import Any, Dict


class DataClassification:
    def classify(self, pii_report: Dict[str, Any]) -> Dict[str, Any]:
        types = {finding["pii_type"] for finding in pii_report.get("pii_findings", [])}
        if {"SSN", "AADHAR", "Credit Card", "Passport"} & types:
            label = "Restricted"
        elif types:
            label = "Confidential"
        elif pii_report.get("pii_risk_score", 0) > 0:
            label = "Internal"
        else:
            label = "Public"
        return {"classification": label, "detected_pii_types": sorted(types)}
