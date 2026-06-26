from typing import Any, Dict, Sequence

from app.tiap.inventory.inventory_parser import InventoryParser


class ComplexityAnalyzer:
    def analyze(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None) -> Dict[str, Any]:
        inventory = InventoryParser().build_inventory(all_jobs, repository_path)
        kpis = inventory.get("kpis", {})
        dependency_edges = sum(len(children) for children in inventory.get("dependencies", {}).values())
        score = min(
            100,
            int(
                kpis.get("total_jobs", 0) * 2
                + kpis.get("total_components", 0) * 0.4
                + kpis.get("total_contexts", 0) * 1.5
                + dependency_edges * 5
                + kpis.get("total_routines", 0) * 3
                + kpis.get("total_joblets", 0) * 4
            ),
        )
        category = "Enterprise" if kpis.get("total_jobs", 0) > 500 else "Large" if kpis.get("total_jobs", 0) > 100 else "Medium" if kpis.get("total_jobs", 0) > 25 else "Small"
        return {
            "repository_complexity_score": score,
            "complexity_level": "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW",
            "sizing_category": category,
            "drivers": {
                "jobs": kpis.get("total_jobs", 0),
                "components": kpis.get("total_components", 0),
                "contexts": kpis.get("total_contexts", 0),
                "dependencies": dependency_edges,
                "routines": kpis.get("total_routines", 0),
                "joblets": kpis.get("total_joblets", 0),
            },
        }
