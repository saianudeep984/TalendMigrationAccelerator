"""Project-wide component usage and risk rankings."""
from collections import defaultdict
from app.analyzers.complexity_analyzer import WEIGHTS
from app.config.component_rules import DEPRECATED_COMPONENT_MAP, TALEND8_KNOWN_COMPONENTS


class ComponentUsageIntelligence:
    def analyze(self, jobs):
        usage = defaultdict(lambda: {"count": 0, "jobs": set()})
        for wrapper in jobs or []:
            data = wrapper.get("job_data", wrapper); name = data.get("job_name", "Unknown")
            for component in data.get("components", []) or []:
                ctype = component.get("component_type", str(component)) if isinstance(component, dict) else str(component)
                usage[ctype]["count"] += 1; usage[ctype]["jobs"].add(name)
        rows = []
        for ctype, item in usage.items():
            risk = WEIGHTS.get(ctype, 5) + (25 if ctype in DEPRECATED_COMPONENT_MAP else 0) + (35 if ctype not in TALEND8_KNOWN_COMPONENTS else 0)
            rows.append({"component": ctype, "count": item["count"], "job_count": len(item["jobs"]),
                         "jobs": sorted(item["jobs"]), "risk_score": min(100, risk),
                         "risk": "CRITICAL" if risk >= 75 else "HIGH" if risk >= 50 else "MEDIUM" if risk >= 25 else "LOW"})
        frequency = sorted(rows, key=lambda x: (-x["count"], x["component"]))
        risk = sorted(rows, key=lambda x: (-x["risk_score"], -x["count"], x["component"]))
        return {"by_frequency": frequency, "by_risk": risk, "heatmap": frequency,
                "highest_risk_components": risk[:10], "total_instances": sum(x["count"] for x in rows)}

    build = analyze
