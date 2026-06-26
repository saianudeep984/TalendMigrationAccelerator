import re
from typing import Any, Dict, Sequence


class PIIScanner:
    PATTERNS = {
        "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|\bemail\b",
        "Phone": r"\b(phone|mobile|contact|tel)\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
        "SSN": r"\bssn\b|\b\d{3}-\d{2}-\d{4}\b",
        "PAN": r"\bpan\b|\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        "AADHAR": r"\baadhaar\b|\baadhar\b|\b\d{4}\s\d{4}\s\d{4}\b",
        "Credit Card": r"\b(card|credit_card|cc_number|credit card)\b",
        "Passport": r"\bpassport\b|\b[A-Z][0-9]{7}\b",
    }

    def scan(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        findings = []
        for job in all_jobs:
            job_name = job.get("job_data", {}).get("job_name", "Unknown")
            for component in job.get("job_data", {}).get("components", []):
                text = " ".join([component.get("component_type", ""), component.get("unique_name", "")] + [str(v) for v in (component.get("parameters") or {}).values()])
                for pii_type, pattern in self.PATTERNS.items():
                    if re.search(pattern, text, re.IGNORECASE) or (pii_type == "Credit Card" and self._has_luhn_card(text)):
                        findings.append({"job": job_name, "component": component.get("component_type", ""), "pii_type": pii_type, "source": "metadata"})
            for ctx in job.get("job_data", {}).get("contexts", []):
                text = " ".join(str(v) for v in ctx.values()) if isinstance(ctx, dict) else str(ctx)
                for pii_type, pattern in self.PATTERNS.items():
                    if re.search(pattern, text, re.IGNORECASE) or (pii_type == "Credit Card" and self._has_luhn_card(text)):
                        findings.append({"job": job_name, "component": "context", "pii_type": pii_type, "source": "context_metadata"})
        score = min(100, len(findings) * 12)
        return {"pii_findings": findings, "pii_risk_score": score, "pii_risk": "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW"}

    def _has_luhn_card(self, text: str) -> bool:
        for candidate in re.findall(r"(?:\d[ -]*?){13,19}", text):
            digits = re.sub(r"\D", "", candidate)
            if len(digits) < 13 or len(set(digits)) == 1:
                continue
            total = 0
            reverse = digits[::-1]
            for index, char in enumerate(reverse):
                value = int(char)
                if index % 2 == 1:
                    value *= 2
                    if value > 9:
                        value -= 9
                total += value
            if total % 10 == 0:
                return True
        return False
