from __future__ import annotations
from .framework_inventory import FrameworkInventoryEngine
from .maturity_analyzer import FrameworkMaturityAnalyzer
from .framework_gap_analyzer import FrameworkGapAnalyzer


class FrameworkBestPracticeAnalyzer:
    def analyze(self, jobs):
        inv = FrameworkInventoryEngine().inventory(jobs)
        maturity = FrameworkMaturityAnalyzer().score(inv)
        gaps = FrameworkGapAnalyzer().analyze(inv, maturity)
        compliance = round(maturity["framework_maturity_score"] * .7 + inv["framework_coverage"] * .3, 1)
        return {"framework_inventory": inv, "framework_maturity": maturity, "framework_gaps": gaps,
                "framework_risks": gaps["architectural_risks"] + gaps["operational_risks"],
                "recommendations": gaps["remediation_recommendations"],
                "best_practice_compliance_score": compliance,
                "standards": ["Talend Best Practices", "Enterprise ETL Standards", "Migration Best Practices"]}
