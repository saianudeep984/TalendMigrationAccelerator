"""
TMA AI Executive Summary
Generates: Business Summary, Technical Summary, Risks, Opportunities, Recommendations
Each section capped at 10 lines. Business/Technical summaries use dedicated rule-based
generation (the shared llm_engine fallback doesn't differentiate prompt intent); Risks,
Opportunities, and Recommendations reuse app.tiap.migration_assessment for grounding.
"""
from __future__ import annotations
from typing import Any

from app.ai.llm_engine import ask_ollama, _check_ollama, _limit_lines
from app.tiap.migration_assessment.migration_assessment import build_migration_assessment

MAX_LINES = 10


def _job_meta(job_data: dict) -> dict:
    components = job_data.get("components", [])
    return {
        "job_name": job_data.get("job_name", "Unknown"),
        "component_count": len(components),
        "component_types": sorted({c.get("component_type", "") for c in components}),
    }


def _ai_or_fallback(prompt: str, fallback_text: str) -> str:
    """Use Ollama if reachable; otherwise use a dedicated, deterministic fallback
    rather than the shared generic llm_engine fallback, which is tuned for a
    different (migration-recommendation) prompt shape.

    ask_ollama() can itself silently return that generic, prompt-blind fallback
    (e.g. on a request timeout or malformed response) even when _check_ollama()
    said the server was reachable — and it does so without raising, so a plain
    try/except here would never catch it. We detect that fallback's fixed
    "**Migration Analysis for:" signature and treat it the same as a failure,
    falling through to this section's own tailored fallback_text instead.
    """
    if _check_ollama():
        try:
            response = ask_ollama(prompt)
            if not response.strip().startswith("**Migration Analysis for:"):
                return _limit_lines(response, max_lines=MAX_LINES)
        except Exception:
            pass
    return _limit_lines(fallback_text, max_lines=MAX_LINES)


# ── Business Summary ──────────────────────────────────────────────────────────

def generate_business_summary(job_data: dict) -> str:
    meta = _job_meta(job_data)
    prompt = (
        "You are a CIO advisor. Write a Business Process Summary in 10 lines or fewer, "
        "plain English, no jargon.\n\n"
        f"Job Name: {meta['job_name']}\n"
        f"Component Count: {meta['component_count']}\n"
        f"Component Types: {', '.join(meta['component_types']) or 'N/A'}"
    )
    fallback = (
        f"- {meta['job_name']} is a data integration job handling {meta['component_count']} processing step(s).\n"
        f"- It moves and transforms data as part of the Talend migration scope.\n"
        f"- Business teams relying on this job's output should validate results after migration."
    )
    return _ai_or_fallback(prompt, fallback)


# ── Technical Summary ─────────────────────────────────────────────────────────

def generate_technical_summary(job_data: dict) -> str:
    meta = _job_meta(job_data)
    prompt = (
        "You are a senior data architect. Write a Technical Summary in 10 lines or fewer "
        "covering data flow, key components, and complexity.\n\n"
        f"Job Name: {meta['job_name']}\n"
        f"Component Count: {meta['component_count']}\n"
        f"Component Types: {', '.join(meta['component_types']) or 'N/A'}"
    )
    fallback = (
        f"- Job: {meta['job_name']}\n"
        f"- Component count: {meta['component_count']}\n"
        f"- Component types used: {', '.join(meta['component_types']) or 'N/A'}"
    )
    return _ai_or_fallback(prompt, fallback)


# ── Risks ──────────────────────────────────────────────────────────────────────

def generate_risks(job_data: dict) -> str:
    assess = build_migration_assessment(job_data)
    risks = assess["migration_risks"]
    if not risks:
        return "- No significant migration risks identified for this job."
    lines = [f"- {r['component']} ({r['risk']}): {r['reason']}" for r in risks]
    return "\n".join(lines[:MAX_LINES])


# ── Opportunities ──────────────────────────────────────────────────────────────

def generate_opportunities(job_data: dict) -> str:
    meta = _job_meta(job_data)
    assess = build_migration_assessment(job_data)
    prompt = (
        "You are a cloud modernization advisor. List up to 10 lines of Optimization "
        "Opportunities for migrating this Talend job to the cloud — focus on simplification, "
        "automation, and modern component replacements.\n\n"
        f"Job Name: {meta['job_name']}\n"
        f"Component Types: {', '.join(meta['component_types']) or 'N/A'}\n"
        f"Cloud Readiness: {assess['cloud_readiness']['readiness']}\n"
        f"Unsupported Components: {[u['category'] for u in assess['unsupported_components']]}"
    )
    unsupported = assess["unsupported_components"]
    if unsupported:
        fallback_lines = [
            f"- Replace or modernize {u['category']} ({u['count']} instance(s)) for cloud compatibility."
            for u in unsupported
        ]
    else:
        fallback_lines = ["- No unsupported components detected; job is already cloud-aligned."]
    fallback_lines.append(f"- Current cloud readiness: {assess['cloud_readiness']['readiness']}.")
    fallback = "\n".join(fallback_lines)
    return _ai_or_fallback(prompt, fallback)


# ── Recommendations ────────────────────────────────────────────────────────────

def generate_recommendations(job_data: dict) -> str:
    assess = build_migration_assessment(job_data)
    recs = assess["recommendations"]
    return "\n".join(f"- {r}" for r in recs[:MAX_LINES])


# ── Master Builder ────────────────────────────────────────────────────────────

def build_executive_summary(job_data: dict) -> dict:
    return {
        "job_name": job_data.get("job_name", "Unknown"),
        "business_summary": generate_business_summary(job_data),
        "technical_summary": generate_technical_summary(job_data),
        "risks": generate_risks(job_data),
        "opportunities": generate_opportunities(job_data),
        "recommendations": generate_recommendations(job_data),
    }
