from typing import Any, Dict, Sequence

from app.tiap.documentation.executive_summary_generator import ExecutiveSummaryGenerator
from app.tiap.documentation.export_utils import export_document
from app.tiap.documentation.functional_doc_generator import FunctionalDocGenerator
from app.tiap.documentation.kt_doc_generator import KTDocGenerator
from app.tiap.documentation.migration_doc_generator import MigrationDocGenerator
from app.tiap.documentation.technical_doc_generator import TechnicalDocGenerator


class RepositoryDocGenerator:
    def generate(
        self,
        all_jobs: Sequence[Dict[str, Any]],
        repository_path: str = None,
        effort: Dict[str, Any] = None,
        technical_template: str = None,
    ) -> Dict[str, str]:
        return {
            "technical": TechnicalDocGenerator().generate(all_jobs, repository_path, technical_template),
            "functional": FunctionalDocGenerator().generate(all_jobs),
            "kt": KTDocGenerator().generate(all_jobs),
            "migration": MigrationDocGenerator().generate(all_jobs),
            "executive": ExecutiveSummaryGenerator().generate(all_jobs, repository_path, effort),
        }

    def combined_markdown(self, all_jobs, repository_path=None, effort=None, technical_template=None) -> str:
        docs = self.generate(all_jobs, repository_path, effort, technical_template)
        return "\n\n---\n\n".join(docs.values())

    def export(self, all_jobs, output_dir, repository_path=None, effort=None, technical_template=None) -> Dict[str, Any]:
        docs = self.generate(all_jobs, repository_path, effort, technical_template)
        exports = {
            "technical": TechnicalDocGenerator().export(all_jobs, output_dir, repository_path, technical_template),
            "functional": FunctionalDocGenerator().export(all_jobs, output_dir),
            "kt": KTDocGenerator().export(all_jobs, output_dir),
            "migration": MigrationDocGenerator().export(all_jobs, output_dir),
            "executive": ExecutiveSummaryGenerator().export(all_jobs, output_dir, repository_path, effort),
        }
        exports["repository"] = export_document(
            output_dir,
            "repository_documentation",
            "Repository Documentation",
            "\n\n---\n\n".join(docs.values()),
        )
        return exports
