from app.ai.context_accessor import get_ai_context
from app.tiap.documentation.functional_doc_generator import FunctionalDocGenerator
from app.tiap.documentation.kt_doc_generator import KTDocGenerator
from app.tiap.documentation.migration_doc_generator import MigrationDocGenerator
from app.tiap.documentation.technical_doc_generator import TechnicalDocGenerator
from app.parser.source_target_extractor import build_source_target_inventory


# ---------------------------------------------------------------------------
# Internal helper — used by canonical generators below
# ---------------------------------------------------------------------------

def _extract_sources_targets(job_data: dict):
    """Return (sources_list, targets_list) using the enhanced extractor."""
    inv = build_source_target_inventory(job_data)
    return inv["source_names"], inv["target_names"]


def _context_job_note(context: dict, job_name: str, field: str) -> str:
    """Extract a per-job or repository-level note from the cached AI context."""
    job_recs = context.get("job_recommendations", {})
    if job_recs:
        for key, val in job_recs.items():
            if str(key).lower() == str(job_name).lower():
                return str(val)
    return context.get(field, "")


# ---------------------------------------------------------------------------
# Canonical Section Provider Registry (F5.2 architecture)
# Each entry: (Layer-1 provider class, AI-context note field).
# generate_doc() is the single canonical entrypoint; the four public
# generate_*_doc() wrappers below are thin convenience aliases over it so
# existing call sites (ai_intelligence_page.py) keep working unchanged.
# ---------------------------------------------------------------------------

_DOC_REGISTRY = {
    "technical":   (TechnicalDocGenerator,  "technical_documentation_notes"),
    "functional":  (FunctionalDocGenerator, "functional_documentation_notes"),
    "kt":          (KTDocGenerator,         "kt_documentation_notes"),
    "migration":   (MigrationDocGenerator,  "migration_assessment"),
}


def generate_doc(doc_type: str, job_data: dict, use_ai: bool = True) -> str:
    """Canonical entrypoint: render any registered doc type for one job,
    overlaying an AI note section when available."""
    provider_cls, note_field = _DOC_REGISTRY[doc_type]
    ctx = get_ai_context() if use_ai else {}
    note = _context_job_note(ctx, job_data.get("job_name", ""), note_field)
    if doc_type == "migration" and not note:
        note = _context_job_note(ctx, job_data.get("job_name", ""), "job_recommendations")
    base = provider_cls().generate([{"job_data": job_data}])
    heading = "### AI Migration Assessment" if doc_type == "migration" else "### AI Notes"
    return base + f"\n\n{heading}\n{note}" if note else base


# ---------------------------------------------------------------------------
# Public API (thin aliases over the canonical registry — signatures preserved)
# ---------------------------------------------------------------------------

def generate_tech_doc(job_data: dict, use_ai: bool = True) -> str:
    return generate_doc("technical", job_data, use_ai)


def generate_functional_doc(job_data: dict, use_ai: bool = True) -> str:
    return generate_doc("functional", job_data, use_ai)


def generate_kt_doc(job_data: dict, use_ai: bool = True) -> str:
    return generate_doc("kt", job_data, use_ai)


def generate_migration_doc(job_data: dict, use_ai: bool = True) -> str:
    return generate_doc("migration", job_data, use_ai)
