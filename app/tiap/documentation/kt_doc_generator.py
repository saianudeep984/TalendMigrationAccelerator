from typing import Any, Dict, Sequence

from app.tiap.documentation.export_utils import export_document
from app.tiap.graph.flowchart_generator import FlowchartGenerator
from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder


class KTDocGenerator:
    def generate(self, all_jobs: Sequence[Dict[str, Any]]) -> str:
        deps = DependencyGraphBuilder().analyze(all_jobs)
        flows = FlowchartGenerator().generate(all_jobs)
        lines = [
            "# Knowledge Transfer Document",
            "",
            "## Overview",
            f"This repository contains {len(all_jobs)} parsed Talend jobs.",
            "",
            "## Execution Flow",
            flows.get("repository_flow", ""),
            "",
            "## Support Notes",
            "- Validate context values before execution.",
            "- Review custom code and deprecated components before cloud deployment.",
            "- Confirm parent-child scheduling order for orchestration jobs.",
            "",
            "## Dependency Summary",
            str(deps.get("dependency_statistics", {})),
        ]
        return "\n".join(lines)

    def export(self, all_jobs, output_dir):
        return export_document(output_dir, "kt_document", "Knowledge Transfer Document", self.generate(all_jobs))
