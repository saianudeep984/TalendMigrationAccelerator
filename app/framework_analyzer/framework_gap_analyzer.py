class FrameworkGapAnalyzer:
    def analyze(self, inventory, maturity=None):
        inv = inventory.get("framework_inventory", {})
        missing = [k for k, v in inv.items() if not v.get("detected")]
        weak = [k for k, v in inv.items() if v.get("detected") and v.get("usage_count", 0) < 2]
        return {"missing_capabilities": missing, "weak_implementations": weak,
                "architectural_risks": [f"Missing {x}" for x in missing[:5]],
                "operational_risks": [x for x in missing if any(y in x for y in ("audit", "error", "logging", "restart"))],
                "remediation_recommendations": [f"Implement enterprise {x.replace('_', ' ')}." for x in missing + weak]}
