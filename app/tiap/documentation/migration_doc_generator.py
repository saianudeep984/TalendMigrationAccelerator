from typing import Any, Dict, Sequence

from app.tiap.documentation.export_utils import export_document
from app.tiap.profiling.component_profiler import ComponentProfiler


class MigrationDocGenerator:
    CLOUD_BLOCKERS = {"tSystem", "tLibraryLoad", "tJava", "tJavaFlex", "tBeanShell"}

    def generate(self, all_jobs: Sequence[Dict[str, Any]]) -> str:
        profile = ComponentProfiler().profile(all_jobs)
        blockers = [
            row for row in profile.get("component_usage", [])
            if row["component"] in self.CLOUD_BLOCKERS
        ]
        lines = [
            "# Migration Documentation",
            "",
            "## Risks",
            f"- Deprecated Components: {len(profile.get('deprecated_components', []))}",
            f"- Custom Components: {len(profile.get('custom_components', []))}",
            f"- Unknown Components: {len(profile.get('unknown_components', []))}",
            "",
            "## Cloud Blockers",
        ]
        lines.extend([f"- {row['component']}: {row['usage_count']} uses" for row in blockers] or ["- None detected"])
        lines.append("")
        lines.append("## Deprecated Components")
        lines.extend([f"- {row['component']}: {row['recommendation']}" for row in profile.get("deprecated_components", [])] or ["- None detected"])
        lines.append("")
        lines.append("## Custom Components")
        lines.extend([f"- {row['component']}: {row['recommendation']}" for row in profile.get("custom_components", [])] or ["- None detected"])
        lines.append("")
        lines.append("## Recommendations")
        lines.extend([
            "- Replace deprecated components using target Talend equivalents.",
            "- Review Java and shell execution before Talend Cloud migration.",
            "- Validate unknown components against the target runtime catalog.",
        ])
        return "\n".join(lines)

    def export(self, all_jobs, output_dir):
        return export_document(output_dir, "migration_documentation", "Migration Documentation", self.generate(all_jobs))
