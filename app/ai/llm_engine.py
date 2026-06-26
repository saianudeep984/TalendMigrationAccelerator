"""
LLM Engine — rule-based fallback (no Ollama dependency required).
Ollama is used if available; otherwise falls back to built-in analysis.
"""

import requests
import hashlib
import logging
import threading
from app.config.ollama_profile_store import OllamaProfileStore

OLLAMA_URL = "http://localhost:11434/api/generate"
_DEFAULT_MODEL = "qwen2.5-coder:3b"
logger = logging.getLogger(__name__)

_OLLAMA_AVAILABLE = None  # cached
_OLLAMA_AVAILABLE_LOCK = threading.Lock()


def get_active_model() -> str:
    """Lazily resolve the active Ollama model at call time (no import-time I/O)."""
    return OllamaProfileStore().get_active().get("model", _DEFAULT_MODEL)


def __getattr__(name: str):
    # Backward-compat: callers that did `from app.ai.llm_engine import OLLAMA_MODEL`
    # get the model resolved lazily on access instead of at import time.
    if name == "OLLAMA_MODEL":
        return get_active_model()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _check_ollama() -> bool:
    global _OLLAMA_AVAILABLE
    with _OLLAMA_AVAILABLE_LOCK:
        if _OLLAMA_AVAILABLE is not None:
            return _OLLAMA_AVAILABLE
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        result = r.status_code == 200
    except requests.exceptions.RequestException as exc:
        logger.info("Ollama unavailable (%s); using built-in fallback.", type(exc).__name__)
        result = False
    except Exception as exc:
        logger.warning("Unexpected Ollama availability error; using built-in fallback: %s", exc)
        result = False
    with _OLLAMA_AVAILABLE_LOCK:
        _OLLAMA_AVAILABLE = result
        return _OLLAMA_AVAILABLE


def _apply_prompt_engineering(prompt: str) -> str:
    """
    Apply prompt-engineering guardrails before sending to Ollama:
      1. Prefix with a conciseness directive so local models don't pad output.
      2. Suffix with a code-only directive when the prompt asks for code changes.
      3. Add an import guard when the prompt mentions imports or files.
    """
    conciseness_prefix = "Be concise. Output only the requested content changes.\n\n"

    needs_code_suffix = any(
        kw in prompt.lower()
        for kw in ("code", "function", "def ", "class ", "script", "snippet", "implement")
    )
    code_only_suffix = "\n\nOnly output code. No explanation." if needs_code_suffix else ""

    needs_import_guard = any(
        kw in prompt.lower()
        for kw in ("import", "from ", "require", "module", "package")
    )
    import_guard = (
        "\n\nOnly import from files that already exist in the project."
        if needs_import_guard
        else ""
    )

    return conciseness_prefix + prompt + code_only_suffix + import_guard


def ask_ollama(prompt: str, use_ollama: bool = True) -> str:
    """Call Ollama if available, otherwise return a structured fallback."""
    prompt = _runtime_prompt_editor(prompt)
    if not use_ollama:
        return _fallback_response(prompt)
    if _check_ollama():
        try:
            _profile = OllamaProfileStore().get_active()
            _model = _profile.get("model", _DEFAULT_MODEL)
            engineered_prompt = _apply_prompt_engineering(prompt)
            payload = {
                "model": _model,
                "prompt": engineered_prompt,
                "stream": False,
                "options": {
                    "temperature": _profile.get("temperature", 0.3),
                    "top_p": _profile.get("top_p", 0.9),
                    "num_predict": _profile.get("max_tokens", 4096),
                    "num_ctx": _profile.get("context_length", 8192),
                }
            }
            if _profile.get("system_prompt"):
                payload["system"] = _profile["system_prompt"]
            response = requests.post(OLLAMA_URL, json=payload, timeout=60)
            result = response.json()
            return result.get("response", _fallback_response(prompt))
        except requests.exceptions.RequestException as exc:
            logger.info("Ollama request failed (%s); using built-in fallback.", type(exc).__name__)
        except Exception as exc:
            logger.warning("Unexpected Ollama request error; using built-in fallback: %s", exc)
    return _fallback_response(prompt)


def _runtime_prompt_editor(prompt: str) -> str:
    """Expose the exact prompt in Streamlit when runtime prompt editing is enabled."""
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx() is None:
            return prompt
        if not st.session_state.get("show_ai_prompt_editor", False):
            return prompt
        digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10]
        with st.expander(f"AI prompt used for this call ({digest})", expanded=False):
            st.caption(f"Ollama model: {get_active_model()}")
            return st.text_area(
                "Prompt",
                value=prompt,
                height=260,
                key=f"runtime_ai_prompt_{digest}",
            )
    except Exception:
        logger.exception("Failed to render runtime prompt editor; using original prompt.")
        return prompt


def _business_fallback(prompt: str) -> str:
    """Plain-language fallback for business-summary prompts (job or component level)."""
    fields = {}
    for line in prompt.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            k, v = k.strip().lower(), v.strip()
            if k and v and len(k) < 40:
                fields[k] = v

    name = fields.get("job name") or fields.get("component name") or "This item"
    what = fields.get("technical summary") or fields.get("what it does") or "processes data as part of the migration"
    sources = fields.get("data sources") or fields.get("what it receives") or ""
    targets = fields.get("data destinations") or fields.get("what it produces") or ""
    complexity = (fields.get("complexity") or fields.get("complexity level") or "").lower()

    if fields.get("technical summary"):
        sentence = fields["technical summary"].rstrip(".") + "."
    else:
        sentence = f"{name} {what[0].lower() + what[1:] if what else ''}".rstrip(".") + "."
        if sources.lower() not in ("", "none detected", "—"):
            sentence += f" It draws on {sources.lower()}"
            sentence += f" and delivers results to {targets.lower()}." if targets.lower() not in ("", "none detected", "—") else "."
        elif targets.lower() not in ("", "none detected", "—"):
            sentence += f" It produces {targets.lower()}."

    ease = {"low": "straightforward to carry forward", "medium": "needs some review",
            "high": "needs careful review", "critical": "needs careful review"}.get(complexity)
    if ease:
        sentence += f" Overall, this is {ease} as part of the migration."
    return sentence


def _limit_lines(text: str, max_lines: int = 3) -> str:
    """Trim a response down to at most `max_lines` non-empty lines."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return "\n".join(lines[:max_lines])


def generate_business_purpose(
    job_name: str,
    technical_summary: str = "",
    sources: list | None = None,
    targets: list | None = None,
    complexity: str = "",
    use_ollama: bool = True,
) -> str:
    """
    Generate a plain-language Business Purpose summary for a job.

    Always returns at most 3 non-empty lines, regardless of whether the
    underlying model (or rule-based fallback) honors the instruction.
    """
    sources = sources or []
    targets = targets or []
    prompt = (
        "You are a business analyst explaining a data integration job to a non-technical stakeholder.\n"
        "Rules: plain business language only, no code or technical component names, describe WHAT the "
        "job accomplishes and WHY it matters (not how). Respond in at most 3 short lines, no bullets, "
        "no headers.\n\n"
        f"Job name: {job_name}\n"
        f"Technical summary: {technical_summary or 'No technical summary available'}\n"
        f"Data sources: {', '.join(sources) or 'none detected'}\n"
        f"Data destinations: {', '.join(targets) or 'none detected'}\n"
        f"Complexity: {complexity or 'unknown'}\n\n"
        "Write a simple business explanation of this job in 3 lines or fewer."
    )
    response = ask_ollama(prompt, use_ollama=use_ollama)
    return _limit_lines(response, max_lines=3)


def _fallback_response(prompt: str) -> str:
    """Rule-based migration recommendation when Ollama is not available."""
    if prompt.strip().lower().startswith("you are a business analyst"):
        return _business_fallback(prompt)
    lines = prompt.split("\n")
    components = []
    job_name = "Unknown"
    for line in lines:
        line = line.strip()
        if line.startswith("Job Name:"):
            job_name = line.replace("Job Name:", "").strip()
        if "'" in line and "t" in line:
            parts = line.replace("'", "").replace("[", "").replace("]", "").replace(",", "").split()
            for p in parts:
                if p.startswith("t") and len(p) > 3:
                    components.append(p)

    risks = []
    recommendations = []
    remediation = []

    HIGH_RISK = {"tJava", "tJavaRow", "tJavaFlex"}
    CLOUD_CONCERN = {"tSystem", "tLibraryLoad", "tRunJob"}
    DEPRECATED = {"tHiveInput", "tHiveOutput", "tPigLoad", "tELTMap"}

    for c in components:
        if any(h in c for h in HIGH_RISK):
            risks.append(f"• {c}: Contains custom Java — review for API compatibility in Talend 8")
            remediation.append(f"• Refactor {c} custom Java to use Talend 8 standard components where possible")
        if any(h in c for h in CLOUD_CONCERN):
            risks.append(f"• {c}: May have OS/environment dependencies — test in cloud environment")
        if any(h in c for h in DEPRECATED):
            risks.append(f"• {c}: Deprecated in Talend 8 — replacement required")
            remediation.append(f"• Replace {c} with Talend 8 supported equivalent")

    if not risks:
        risks.append("• No high-risk components detected — standard migration path applicable")

    if not recommendations:
        recommendations = [
            "• Use Talend 8 Studio Import Wizard with the original Open Studio ZIP",
            "• Allow internal migration tasks to complete fully before making edits",
            "• Validate context variables after migration — context links are rebuilt by Studio",
            "• Re-test all job connections and metadata after migration",
        ]

    if not remediation:
        remediation = ["• No critical remediation steps required — verify job execution after import"]

    return (
        f"**Migration Analysis for: {job_name}**\n\n"
        f"**Migration Risks:**\n" + "\n".join(risks) + "\n\n"
        f"**Cloud Migration Recommendations:**\n" + "\n".join(recommendations) + "\n\n"
        f"**Required Remediation Steps:**\n" + "\n".join(remediation) + "\n\n"
        f"**Best Practices:**\n"
        f"• Always migrate using the original Open Studio export ZIP — do not pre-modify\n"
        f"• Run migration in a test environment before production\n"
        f"• Document any manual steps for context and metadata fixes\n"
        f"• Validate all context variables and connections post-migration\n"
        f"\n_Note: AI recommendations generated by built-in rule engine. "
        f"Configure Ollama locally for LLM-powered analysis._"
    )


def generate_executive_summary(
    repository_name: str = "",
    total_jobs: int = 0,
    migration_readiness: int | float = 0,
    cloud_readiness: int | float = 0,
    high_risks: int = 0,
    use_ollama: bool = True,
) -> str:
    """Generate a leadership-focused executive summary (max 5 lines)."""
    prompt = (
        "You are a CIO advisor. Create an executive summary in 5 lines or fewer. "
        "Focus on migration readiness, cloud readiness, portfolio scale, risks, and next steps.\n\n"
        f"Repository: {repository_name}\n"
        f"Total Jobs: {total_jobs}\n"
        f"Migration Readiness: {migration_readiness}%\n"
        f"Cloud Readiness: {cloud_readiness}%\n"
        f"High Risks: {high_risks}"
    )
    response = ask_ollama(prompt, use_ollama=use_ollama)
    return _limit_lines(response, max_lines=5)


def generate_business_rules_summary(content: str) -> str:
    """Generate Business Rules summary (max 5 bullets)."""
    prompt = f"""
Summarize the business rules from the content below.
Return maximum 5 bullet points.
Content:
{content}
"""
    try:
        result = ask_ollama(prompt)
        lines = [l.strip() for l in str(result).splitlines() if l.strip()]
        bullets = []
        for line in lines:
            if not line.startswith(("-", "*", "•")):
                line = f"- {line.lstrip('-*• ').strip()}"
            bullets.append(line)
            if len(bullets) >= 5:
                break
        return "\n".join(bullets)
    except Exception:
        return ""


def _clean_system_name(name: str):
    return str(name).strip() if name else ""
