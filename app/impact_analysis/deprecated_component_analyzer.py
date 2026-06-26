"""Talend 7.x to 8.x component compatibility intelligence."""
from app.config.component_rules import DEPRECATED_COMPONENT_MAP, TALEND8_KNOWN_COMPONENTS
from app.analyzers.unsupported_component_analyzer import analyze_unsupported_components


class DeprecatedComponentAnalyzer:
    EFFORT = {"LOW": 2, "MEDIUM": 4, "HIGH": 8, "CRITICAL": 12}

    def analyze(self, jobs, routine_analysis=None):
        unsupported = analyze_unsupported_components(jobs, routine_analysis)
        unsupported_types = {}
        for category, item in unsupported.get("categories", {}).items():
            for instance in item.get("instances", []):
                for ctype in instance.get("breakdown", {}): unsupported_types[ctype] = category
        findings = []
        for wrapper in jobs or []:
            data = wrapper.get("job_data", wrapper); job = data.get("job_name", "Unknown")
            for component in data.get("components", []) or []:
                ctype = component.get("component_type", str(component)) if isinstance(component, dict) else str(component)
                rule = DEPRECATED_COMPONENT_MAP.get(ctype)
                status = "DEPRECATED" if rule else "UNSUPPORTED" if ctype not in TALEND8_KNOWN_COMPONENTS or ctype in unsupported_types else None
                if not status: continue
                risk = (rule or {}).get("risk", "HIGH" if status == "UNSUPPORTED" else "MEDIUM").upper()
                replacement = (rule or {}).get("replacement") or self._replacement(ctype)
                findings.append({"job_name": job, "component": ctype, "status": status, "risk": risk,
                                 "replacement": replacement, "auto_fix": bool((rule or {}).get("auto_fix")),
                                 "recommendation": f"Replace {ctype} with {replacement} and regression-test dependent flows.",
                                 "remediation_hours": self.EFFORT.get(risk, 8)})
        return {"findings": findings, "unsupported_analysis": unsupported,
                "summary": {"total": len(findings), "deprecated": sum(f["status"] == "DEPRECATED" for f in findings),
                            "unsupported": sum(f["status"] == "UNSUPPORTED" for f in findings),
                            "remediation_hours": sum(f["remediation_hours"] for f in findings),
                            "jobs_impacted": len({f["job_name"] for f in findings})}}

    @staticmethod
    def _replacement(ctype):
        if ctype.startswith("tJava"): return "tMap or shared routine"
        if ctype.startswith("tJDBC"): return "Talend 8 named database connector"
        if ctype == "tSystem": return "cloud function or managed API"
        return "Talend 8 supported equivalent"

    analyze_components = analyze
