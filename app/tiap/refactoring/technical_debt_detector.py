import os
from typing import Any, Dict, Sequence

from app.tiap.models.repository import write_json
from app.tiap.refactoring.component_standardizer import ComponentStandardizer
from app.tiap.refactoring.context_consolidator import ContextConsolidator
from app.tiap.refactoring.java_refactor import JavaRefactor


class TechnicalDebtDetector:
    def analyze(self, all_jobs: Sequence[Dict[str, Any]], output_dir: str = None) -> Dict[str, Any]:
        java = JavaRefactor().analyze(all_jobs)
        contexts = ContextConsolidator().analyze(all_jobs)
        components = ComponentStandardizer().analyze(all_jobs)
        score = min(
            100,
            len(java.get("tjava_analysis", [])) * 12
            + len(contexts.get("context_consolidation", [])) * 8
            + len(components.get("component_standardization", [])) * 10,
        )
        result = {
            "debt_score": score,
            "debt_level": "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW",
            "java_refactoring": java,
            "context_consolidation": contexts,
            "component_standardization": components,
        }
        if output_dir:
            write_json(os.path.join(output_dir, "refactoring_report.json"), result)
        return result
