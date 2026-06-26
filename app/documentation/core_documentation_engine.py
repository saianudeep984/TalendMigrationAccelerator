"""
Canonical Documentation Engine.

Defines the shared interfaces for the 3-layer documentation architecture
(F5.2): Section Providers -> Orchestrator -> Renderers/Exporters. Existing
generators (tdd_sections, ai_doc_generator, report_pack_generator,
technical_doc_generator, export_utils, template_manager) implement or wrap
these protocols; this module does not duplicate their logic, only the
contracts they share.

New documentation features should depend on these interfaces rather than
importing a specific generator/orchestrator/exporter directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Protocol, Sequence, runtime_checkable


# ---------------------------------------------------------------------------
# Layer 1 — Section Providers
# ---------------------------------------------------------------------------

@runtime_checkable
class SectionProvider(Protocol):
    """A unit of content generation for one job or one repository.

    Implementations: tdd_sections.generate_*_section, ai_doc_generator's
    registry entries, technical_doc_generator.TechnicalDocGenerator,
    functional/kt/migration_doc_generator, executive_summary_generator.
    """

    def generate(self, data: Mapping[str, Any]) -> Any:
        """Return section content. May be markdown (str) or a structured
        dict (e.g. {"findings": [...]})."""
        ...


@dataclass
class SectionResult:
    """Normalized wrapper so heterogeneous provider outputs (str vs dict)
    can be handled uniformly by an orchestrator without losing the
    provider's native shape."""

    key: str
    content: Any  # str (markdown) or dict (structured findings)
    is_markdown: bool = False

    def as_markdown(self) -> str:
        if self.is_markdown:
            return str(self.content)
        if isinstance(self.content, dict) and "findings" in self.content:
            findings = self.content["findings"] or []
            return "\n".join(f"- {f}" for f in findings) if findings else "- None"
        return str(self.content)


class SectionRegistry(ABC):
    """A named collection of SectionProviders forming one document family
    (e.g. all TDD quality sections, or all report-pack sections).

    Concrete registries: tdd_sections._build_section_registry(),
    ai_doc_generator._DOC_REGISTRY (adapted), report_pack_generator's
    section dict in build_report_pack_sections().
    """

    @abstractmethod
    def providers(self) -> Dict[str, SectionProvider]:
        """Return {section_key: provider}."""
        ...

    def generate_all(self, data: Mapping[str, Any]) -> Dict[str, Any]:
        """Run every registered provider against the same input data."""
        return {key: provider.generate(data) for key, provider in self.providers().items()}


# ---------------------------------------------------------------------------
# Layer 2 — Orchestrators
# ---------------------------------------------------------------------------

@dataclass
class DocumentPack:
    """Output of an orchestrator: assembled sections plus the paths of
    every exported format."""

    sections: Dict[str, Any]
    output_paths: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentOrchestrator(ABC):
    """Assembles a SectionRegistry's output into a DocumentPack and drives
    export via Renderer/Exporter implementations.

    Concrete orchestrators: tdd_export.export_tdd, report_pack_generator
    .build_report_pack, RepositoryDocGenerator. Each targets a different
    scope (single-job TDD, full-repository pack, per-job doc set) but must
    conform to this interface so callers (UI pages) can swap orchestrators
    without changing call sites.
    """

    @abstractmethod
    def build_sections(self, data: Mapping[str, Any]) -> Dict[str, Any]:
        """Assemble raw section content (markdown or structured) — Layer 1."""
        ...

    @abstractmethod
    def export(self, data: Mapping[str, Any], output_dir: str, formats: Sequence[str]) -> DocumentPack:
        """Render and write the requested formats — delegates to Layer 3."""
        ...


# ---------------------------------------------------------------------------
# Layer 3 — Renderers / Exporters
# ---------------------------------------------------------------------------

@runtime_checkable
class MarkdownRenderer(Protocol):
    """Converts markdown to another format. Implementations:
    export_utils.markdown_to_html (full document, mermaid-aware),
    export_utils.markdown_fragment_to_html (embeddable fragment),
    export_utils.write_docx, export_utils.write_pdf.
    """

    def render(self, markdown: str, title: str = "") -> str:
        ...


@runtime_checkable
class DocumentExporter(Protocol):
    """Writes one or more rendered formats to disk and returns their paths.
    Implementations: export_utils.export_document, reports.excel_export
    .write_complete_assessment_excel, reports.json_export
    .write_complete_assessment_json, template_manager.render_template_docx.
    """

    def export(self, output_dir: str, basename: str, **kwargs: Any) -> Dict[str, str]:
        ...


SUPPORTED_FORMATS = ("markdown", "html", "pdf", "docx", "excel", "json")


# ---------------------------------------------------------------------------
# Convenience: adapt a plain callable into a SectionProvider
# ---------------------------------------------------------------------------

class CallableSectionProvider:
    """Wraps an existing function (e.g. tdd_sections.generate_validation_section)
    so it satisfies the SectionProvider protocol without modifying the
    original function."""

    def __init__(self, fn):
        self._fn = fn

    def generate(self, data: Mapping[str, Any]) -> Any:
        return self._fn(data)


def section_result(key: str, content: Any, is_markdown: bool = False) -> SectionResult:
    """Factory matching the dataclass — used by orchestrators normalizing
    provider output before assembly."""
    return SectionResult(key=key, content=content, is_markdown=is_markdown)
