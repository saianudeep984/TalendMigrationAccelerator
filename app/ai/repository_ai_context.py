import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, Sequence

from app.ai.llm_engine import OLLAMA_MODEL, ask_ollama


REPOSITORY_AI_CONTEXT_FILENAME = "repository_ai_context.json"
REPOSITORY_AI_CONTEXT_SESSION_KEY = "repository_ai_context"


def generate_repository_ai_context(
    all_jobs: Sequence[Dict[str, Any]],
    output_dir: str = "output",
    use_ollama: bool = True,
    prompt_template: str = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    cache_path = os.path.join(output_dir, REPOSITORY_AI_CONTEXT_FILENAME)
    fingerprint = _repository_fingerprint(all_jobs)

    if not force_refresh:
        cached = load_repository_ai_context(cache_path)
        if (
            cached
            and cached.get("repository_fingerprint") == fingerprint
            and cached.get("model") == OLLAMA_MODEL
            and bool(cached.get("use_ollama")) == bool(use_ollama)
        ):
            cached["cache_hit"] = True
            return cached

    prompt = build_repository_ai_prompt(all_jobs, prompt_template)
    raw_response = ask_ollama(prompt, use_ollama=use_ollama) if use_ollama else ""
    context = _parse_or_fallback(raw_response, all_jobs)
    context.update({
        "repository_fingerprint": fingerprint,
        "model": OLLAMA_MODEL,
        "use_ollama": bool(use_ollama),
        "cache_hit": False,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "raw_response": raw_response,
    })
    save_repository_ai_context(context, cache_path)
    return context


def load_repository_ai_context(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def save_repository_ai_context(context: Dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(context, handle, indent=4)
    return path


def build_repository_ai_prompt(all_jobs: Sequence[Dict[str, Any]], prompt_template: str = None) -> str:
    summary = _repository_summary(all_jobs)
    template = prompt_template or _default_repository_prompt()
    try:
        return template.format(repository_summary=json.dumps(summary, indent=2))
    except Exception:
        return _default_repository_prompt().format(repository_summary=json.dumps(summary, indent=2))


def apply_repository_ai_context(all_jobs: Sequence[Dict[str, Any]], context: Dict[str, Any]) -> None:
    job_recommendations = context.get("job_recommendations", {})
    default_recommendations = context.get("recommendations", "")
    for job in all_jobs:
        job_name = job.get("job_data", {}).get("job_name", "Unknown")
        job["ai_recommendation"] = (
            job_recommendations.get(job_name)
            or _find_case_insensitive(job_recommendations, job_name)
            or default_recommendations
            or "AI recommendation unavailable."
        )


def _default_repository_prompt() -> str:
    return """You are a Talend 8 and Talend Cloud migration architect.

Analyze the complete repository summary below once and return concise JSON only.

Repository summary:
{repository_summary}

Return this JSON shape:
{{
  "executive_summary": "...",
  "repository_overview": "...",
  "readiness_scores": "...",
  "technical_flowchart_notes": "...",
  "business_flowchart_notes": "...",
  "repository_flowchart_notes": "...",
  "technical_documentation_notes": "...",
  "functional_documentation_notes": "...",
  "kt_documentation_notes": "...",
  "migration_assessment": "...",
  "component_recommendations": "...",
  "recommendations": "...",
  "test_cases": "markdown table of recommended test cases per job",
  "routine_assessment": "markdown summary of routine complexity and reuse",
  "joblet_assessment": "markdown summary of joblet usage and migration risk",
  "java_risk": "markdown summary of Java version risks and deprecated APIs",
  "doc_readiness": "markdown summary of documentation readiness score per category",
  "job_recommendations": {{"JobName": "..."}}
}}

Do not include markdown fences. Do not ask follow-up questions.
"""


def _repository_summary(all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    jobs = []
    component_counts: Dict[str, int] = {}
    high_risk_count = 0
    for job in all_jobs:
        data = job.get("job_data", job)
        components = [
            c.get("component_type", "UNKNOWN")
            for c in data.get("components", [])
            if isinstance(c, dict)
        ]
        for component in components:
            component_counts[component] = component_counts.get(component, 0) + 1
        high_risk_count += sum(
            1 for risk in job.get("enterprise_risk_report", [])
            if risk.get("risk") in ("HIGH", "CRITICAL")
        )
        jobs.append({
            "job_name": data.get("job_name", "Unknown"),
            "component_count": len(components),
            "components": components[:35],
            "complexity": job.get("complexity", {}),
            "cloud_readiness": job.get("cloud_readiness", {}),
            "dependencies": job.get("dependencies", {}),
            "enterprise_risks": job.get("enterprise_risk_report", [])[:20],
        })
    return {
        "total_jobs": len(all_jobs),
        "total_components": sum(row["component_count"] for row in jobs),
        "high_or_critical_risk_count": high_risk_count,
        "top_components": sorted(
            component_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:25],
        "jobs": jobs,
    }


def _repository_fingerprint(all_jobs: Sequence[Dict[str, Any]]) -> str:
    payload = json.dumps(_repository_summary(all_jobs), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_or_fallback(raw_response: str, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    parsed = _parse_json_response(raw_response)
    if parsed:
        return _normalize_context(parsed, all_jobs)
    return _fallback_context(all_jobs)


def _parse_json_response(raw_response: str) -> Dict[str, Any]:
    if not raw_response:
        return {}
    text = raw_response.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _normalize_context(context: Dict[str, Any], all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    fallback = _fallback_context(all_jobs)
    normalized = {}
    for key, fallback_value in fallback.items():
        value = context.get(key, fallback_value)
        normalized[key] = value if isinstance(value, type(fallback_value)) else fallback_value
    return normalized


def _fallback_context(all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total_jobs = len(all_jobs)
    total_components = sum(
        len(job.get("job_data", job).get("components", []))
        for job in all_jobs
    )
    high_risks = sum(
        1 for job in all_jobs for risk in job.get("enterprise_risk_report", [])
        if risk.get("risk") in ("HIGH", "CRITICAL")
    )
    summary = (
        f"Repository contains {total_jobs} jobs and {total_components} components. "
        f"{high_risks} high or critical risk signals require review before migration."
    )
    recommendations = (
        "Prioritize high-risk components, validate context values and metadata, "
        "run Talend 8 import in a controlled environment, and execute regression tests."
    )
    job_recommendations = {}
    for job in all_jobs:
        data = job.get("job_data", job)
        components = [
            c.get("component_type", "")
            for c in data.get("components", [])
            if isinstance(c, dict)
        ]
        job_recommendations[data.get("job_name", "Unknown")] = (
            f"Review {len(components)} components, validate dependencies, and confirm "
            "Talend 8 runtime compatibility before cutover."
        )
    return {
        "executive_summary": summary,
        "repository_overview": summary,
        "readiness_scores": "Use generated readiness scores as the migration baseline.",
        "technical_flowchart_notes": "Validate technical flow against Talend Studio screenshots and runtime links.",
        "business_flowchart_notes": "Confirm source-to-target business meaning with stakeholders.",
        "repository_flowchart_notes": "Use dependency flow to sequence remediation and testing.",
        "technical_documentation_notes": "Focus review on custom code, context variables, and dependencies.",
        "functional_documentation_notes": "Confirm business rules, source systems, target systems, and expected outputs.",
        "kt_documentation_notes": "Use the generated KT pack for handover and operational support.",
        "migration_assessment": recommendations,
        "component_recommendations": recommendations,
        "recommendations": recommendations,
        "job_recommendations": job_recommendations,
    }


def _find_case_insensitive(values: Dict[str, str], key: str) -> str:
    lowered = str(key).lower()
    for candidate, value in values.items():
        if str(candidate).lower() == lowered:
            return value
    return ""
