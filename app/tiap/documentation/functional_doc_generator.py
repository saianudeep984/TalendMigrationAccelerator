from typing import Any, Dict, Sequence

from app.tiap.documentation.export_utils import export_document
from app.tiap.models.repository import component_parameters, iter_job_data


class FunctionalDocGenerator:
    SOURCE_PREFIXES = ("tFileInput", "tDBInput", "tOracleInput", "tMysqlInput", "tMSSqlInput", "tJDBCInput", "tRESTClient")
    TARGET_PREFIXES = ("tFileOutput", "tDBOutput", "tOracleOutput", "tMysqlOutput", "tMSSqlOutput", "tJDBCOutput")
    RULE_COMPONENTS = {"tMap", "tFilterRow", "tAggregateRow", "tJoin", "tNormalize", "tDenormalize", "tUniqueRow"}

    def generate(self, all_jobs: Sequence[Dict[str, Any]]) -> str:
        lines = ["# Functional Documentation", ""]
        for data in iter_job_data(all_jobs):
            job_name = data.get("job_name", "Unknown")
            sources, targets, rules = [], [], []
            for component in data.get("components", []):
                ctype = component.get("component_type", "")
                params = component_parameters(component)
                label = params.get("TABLE") or params.get("TABLE_NAME") or params.get("FILE_NAME") or params.get("QUERY") or ctype
                if ctype.startswith(self.SOURCE_PREFIXES):
                    sources.append(label)
                if ctype.startswith(self.TARGET_PREFIXES):
                    targets.append(label)
                if ctype in self.RULE_COMPONENTS:
                    rules.append(ctype)
            lines.extend([
                f"## {job_name}",
                f"- Purpose: Move and transform data from detected source systems to detected target systems.",
                f"- Source Systems: {', '.join(sorted(set(sources))) or 'Not detected'}",
                f"- Target Systems: {', '.join(sorted(set(targets))) or 'Not detected'}",
                f"- Business Rules: {', '.join(sorted(set(rules))) or 'No transformation rule components detected'}",
                f"- Expected Outputs: {', '.join(sorted(set(targets))) or 'Validate target components manually'}",
                "",
            ])
        return "\n".join(lines)

    def export(self, all_jobs, output_dir):
        return export_document(output_dir, "functional_documentation", "Functional Documentation", self.generate(all_jobs))
