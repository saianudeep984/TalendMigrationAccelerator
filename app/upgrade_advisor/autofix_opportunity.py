from __future__ import annotations
from app.autofix.autofix_generator import AutoFixGenerator
from app.autofix.rule_engine import AutoFixRuleEngine


class AutoFixOpportunityAnalyzer:
    def analyze(self, jobs, architecture=None):
        recs = AutoFixGenerator().generate(jobs, architecture or {})
        rules = AutoFixRuleEngine().analyze_components(jobs)
        issues = list(recs.get("recommendations", [])) + list(rules.get("upgrade_recommendations", []))
        auto = [
            x for x in issues
            if x.get("auto_fix_available", x.get("auto_fixable", x.get("confidence", 0) >= 70))
        ]
        total = len(issues)
        return {"auto_fix_coverage_percent": round(len(auto) / max(1, total) * 100, 1), "auto_fixable_issues": auto,
                "manual_issues": [x for x in issues if x not in auto], "auto_fix_recommendations": issues}

