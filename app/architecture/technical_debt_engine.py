"""Technical debt scoring and remediation prioritization."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


class TechnicalDebtEngine:
    EFFORT = {"LOW": 2, "MEDIUM": 5, "HIGH": 10, "CRITICAL": 16}

    def calculate(self, anti_patterns: Dict[str, Any], migration_intelligence: Dict[str, Any] = None) -> Dict[str, Any]:
        migration_intelligence = migration_intelligence or {}
        findings = list(anti_patterns.get("findings", []) or [])
        by_asset = defaultdict(lambda: {"asset": "", "risk_points": 0, "findings": 0, "highest_severity": "LOW"})
        sev_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        for f in findings:
            asset = f.get("asset", "repository")
            row = by_asset[asset]
            row["asset"] = asset
            row["risk_points"] += int(f.get("risk_points", 0))
            row["findings"] += 1
            if sev_rank.get(f.get("severity", "LOW"), 1) > sev_rank[row["highest_severity"]]:
                row["highest_severity"] = f.get("severity", "LOW")

        complexity_jobs = (migration_intelligence.get("complexity") or {}).get("jobs", [])
        for job in complexity_jobs:
            if job.get("score", 0) >= 100:
                row = by_asset[job.get("job_name", "Unknown")]
                row["asset"] = job.get("job_name", "Unknown")
                row["risk_points"] += min(25, int(job.get("score", 0) / 10))
                row["findings"] += 1
                row["highest_severity"] = "HIGH"

        assets = sorted(by_asset.values(), key=lambda x: (-x["risk_points"], x["asset"]))
        score = min(100, sum(a["risk_points"] for a in assets))
        items: List[Dict[str, Any]] = []
        for a in assets:
            sev = a["highest_severity"]
            items.append({
                **a,
                "priority": "P1" if sev in {"HIGH", "CRITICAL"} else "P2" if a["risk_points"] >= 10 else "P3",
                "estimated_hours": self.EFFORT.get(sev, 4) + a["findings"],
                "recommendation": "Refactor, externalize configuration, and add regression coverage before migration.",
            })
        return {
            "technical_debt_score": score,
            "technical_debt_band": "LOW" if score < 30 else "MEDIUM" if score < 60 else "HIGH",
            "highest_risk_assets": items[:10],
            "remediation_items": items,
            "estimated_hours": sum(i["estimated_hours"] for i in items),
        }

