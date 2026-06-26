from typing import Any, Dict, Sequence

from app.config.component_rules import DEPRECATED_COMPONENT_MAP


class ComponentStandardizer:
    def analyze(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        rows = []
        for job in all_jobs:
            job_name = job.get("job_data", {}).get("job_name", "Unknown")
            for component in job.get("job_data", {}).get("components", []):
                ctype = component.get("component_type", "")
                if ctype in DEPRECATED_COMPONENT_MAP:
                    rule = DEPRECATED_COMPONENT_MAP[ctype]
                    rows.append({
                        "job": job_name,
                        "component": ctype,
                        "replacement": rule["replacement"],
                        "auto_fix": rule["auto_fix"],
                        "risk": rule["risk"],
                    })
        return {"deprecated_components": rows, "component_standardization": rows}
