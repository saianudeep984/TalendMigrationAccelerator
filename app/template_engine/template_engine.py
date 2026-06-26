import json
import logging
from pathlib import Path
from .template_manager import TemplateManager
from .docx_renderer import DocxRenderer

logger = logging.getLogger(__name__)


def _read(path: Path) -> str:
    return path.read_text(errors="ignore") if path.exists() else ""


def _json_to_md_table(path: Path, section_key: str = None) -> str:
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(errors="ignore"))
        if section_key:
            data = data.get(section_key, data)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [[str(row.get(h, "")) for h in headers] for row in data]
            lines = ["| " + " | ".join(headers) + " |",
                     "| " + " | ".join(["---"] * len(headers)) + " |"]
            lines += ["| " + " | ".join(r) + " |" for r in rows]
            return "\n".join(lines)
        if isinstance(data, dict):
            lines = ["| Key | Value |", "| --- | --- |"]
            lines += [f"| {k} | {v} |" for k, v in data.items()]
            return "\n".join(lines)
        return str(data)
    except Exception:
        logger.exception("Failed to convert JSON data to markdown table.")
        return ""


def _readiness_md(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(errors="ignore"))
        score = data.get("readiness_score", data.get("overall_score", "N/A"))
        return f"**Overall Readiness Score:** {score}\n\n" + _json_to_md_table(path)
    except Exception:
        logger.exception("Failed to render readiness markdown.")
        return ""


class TemplateEngine:

    def __init__(self, output_dir="output"):
        self.output_dir = Path(output_dir)
        self.template_manager = TemplateManager()

    def build_content_map(self):
        o = self.output_dir
        return {
            "{{EXECUTIVE_SUMMARY}}":    _read(o / "executive_summary.md"),
            "{{REPOSITORY_OVERVIEW}}":  _read(o / "repository_documentation.md"),
            "{{REPOSITORY_STATISTICS}}":_json_to_md_table(o / "repository_summary.json"),
            "{{REPOSITORY_FLOWCHART}}": _read(o / "mermaid.mmd"),
            "{{TECHNICAL_DOC}}":        _read(o / "technical_documentation.md"),
            "{{FUNCTIONAL_DOC}}":       _read(o / "functional_documentation.md"),
            "{{KT_DOC}}":               _read(o / "kt_document.md"),
            "{{MIGRATION_ASSESSMENT}}": _read(o / "migration_documentation.md"),
            "{{TEST_CASES}}":           _json_to_md_table(o / "testing_suite.json"),
            "{{ROUTINE_ASSESSMENT}}":   _json_to_md_table(o / "refactoring_report.json", "routines"),
            "{{JOBLET_ASSESSMENT}}":    _json_to_md_table(o / "repository_inventory.json", "joblets"),
            "{{JAVA_RISK}}":            _json_to_md_table(o / "migration_assessment.json", "java_risks"),
            "{{DOC_READINESS}}":        _readiness_md(o / "repository_summary.json"),
            "{{RECOMMENDATIONS}}":      _json_to_md_table(o / "migration_assessment.json", "recommendations"),
            "{{APPENDIX}}":             _json_to_md_table(o / "repository_inventory.json") + "\n\n" +
                                        _json_to_md_table(o / "dependency_summary.json"),
        }

    def generate(self):
        template = self.template_manager.get_active_template()
        renderer = DocxRenderer()
        output_docx = self.output_dir / "Complete_Assessment.docx"
        renderer.render(template, self.build_content_map(), output_docx)
        return str(output_docx)
