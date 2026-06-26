from __future__ import annotations

import re
from typing import Any

# ── Component classification sets ────────────────────────────────────────────

_NATIVE_PATTERNS: list[str] = [
    "tFileInput", "tFileOutput",
    "tJDBC",
    "tDB",
    "tMap",
    "tFilterRow",
    "tAggregate",
    "tJoin",
    "tSortRow",
    "tUniqRow",
    "tReplicate",
    "tLogRow",
    "tFlowMeter",
]

_BLOCKER_PATTERNS: list[str] = [
    "tJava",
    "tBeanShell",
    "tSystem",
    "tLibraryLoad",
    "tDBSP",
    "tDBBulkExec",
    "BulkExec",
    "tAS400",
    "tMainframe",
    "tSalesforceInput",   # proprietary connectors that Qlik can't replace natively
    "tSalesforceOutput",
    "tSAP",
    "tHDFS",
    "tPigLoad",
    "tHive",
    "tKafka",
    "tAzure",
    "tGoogleStorage",
    "tS3",
]

# These are sub-patterns of "tJDBC" but specifically custom/connector usage
_CUSTOM_JDBC_PATTERNS: list[str] = [
    "tJDBCInput",
    "tJDBCOutput",
    "tJDBCRow",
    "tJDBCClose",
    "tJDBCCommit",
    "tJDBCConnection",
    "tJDBCRollback",
]

_RUNJOB = "tRunJob"


def _matches_any(component_type: str, patterns: list[str]) -> bool:
    ct = component_type.lower()
    return any(ct.startswith(p.lower()) or p.lower() in ct for p in patterns)


def _is_native(component_type: str) -> bool:
    return _matches_any(component_type, _NATIVE_PATTERNS)


def _is_blocker(component_type: str) -> bool:
    return _matches_any(component_type, _BLOCKER_PATTERNS)


def _is_runjob(component_type: str) -> bool:
    return component_type.lower().startswith(_RUNJOB.lower())


def _is_custom_jdbc(component_type: str) -> bool:
    return _matches_any(component_type, _CUSTOM_JDBC_PATTERNS)


# ── Core scoring logic ────────────────────────────────────────────────────────

def _score_job(components: list[dict]) -> tuple[int, list[str], list[str]]:
    """Return (raw_score_0_to_100, native_types, blocker_types)."""
    if not components:
        return 50, [], []

    types: list[str] = [
        c.get("component_type", "") for c in components if c.get("component_type")
    ]
    if not types:
        return 50, [], []

    total = len(types)

    native_set: set[str] = set()
    blocker_set: set[str] = set()
    runjob_count = 0
    tmap_expression_count = 0

    for c in components:
        ct: str = c.get("component_type", "")
        if not ct:
            continue
        if _is_blocker(ct):
            blocker_set.add(ct)
        elif _is_runjob(ct):
            runjob_count += 1
        elif _is_native(ct):
            native_set.add(ct)

        # Count tMap expressions as a proxy for complexity
        if ct.lower().startswith("tmap"):
            expr_count = len(c.get("expressions", [])) if isinstance(c.get("expressions"), list) else 0
            tmap_expression_count += expr_count

    native_count = sum(1 for t in types if _is_native(t) and not _is_blocker(t))
    blocker_count = sum(1 for t in types if _is_blocker(t))
    runjob_chain_penalty = max(0, runjob_count - 3) * 8
    tmap_expr_penalty = max(0, tmap_expression_count - 20) * 2

    native_ratio = native_count / total if total else 0
    blocker_ratio = blocker_count / total if total else 0

    base_score = int(native_ratio * 100)
    blocker_penalty = int(blocker_ratio * 60)
    score = max(0, min(100, base_score - blocker_penalty - runjob_chain_penalty - tmap_expr_penalty))

    # Reclamp based on absolute presence of blockers
    if blocker_count > 0 and score > 74:
        score = 74
    if blocker_count > max(1, total // 3) and score > 39:
        score = 39

    # Demote custom JDBC-heavy jobs to MANUAL territory
    custom_jdbc_count = sum(1 for t in types if _is_custom_jdbc(t))
    if custom_jdbc_count >= 3 and score > 39:
        score = 39

    return score, sorted(native_set), sorted(blocker_set)


def _bucket(score: int, has_blockers: bool, runjob_count: int) -> tuple[str, str, str, str, str]:
    """Return (qlik_path, qlik_rag, recommendation, migration_tool)."""
    if score >= 75 and not has_blockers and runjob_count <= 3:
        return (
            "QLIK_NATIVE",
            "GREEN",
            "Qlik Cloud Pipeline — direct lift",
            "Qlik Cloud Pipeline",
        )
    elif score >= 40:
        return (
            "QLIK_PARTIAL",
            "AMBER",
            "Qlik Replicate for data movement, manual rewrite for custom logic",
            "Qlik Replicate + Manual",
        )
    else:
        return (
            "MANUAL_REWRITE",
            "RED",
            "Full rewrite required — Qlik cannot replace natively",
            "Manual Rewrite",
        )


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_qlik_readiness(all_jobs: list[dict]) -> list[dict]:
    """
    Analyse each Talend job for Qlik migration readiness.

    Parameters
    ----------
    all_jobs : list[dict]
        Each element is a job dict as produced by the TMA analysis pipeline.
        Expects ``job["job_data"]["components"]`` to be a list of component
        dicts, each with at minimum a ``"component_type"`` key.

    Returns
    -------
    list[dict]
        One result dict per job with keys:
        job_name, qlik_path, qlik_score, qlik_rag,
        native_components, blocker_components,
        recommendation, migration_tool.
    """
    if not all_jobs:
        return []

    results: list[dict[str, Any]] = []

    for job in all_jobs:
        try:
            job_data: dict = job.get("job_data") or {}
            job_name: str = job_data.get("job_name") or job.get("job_name") or "Unknown"
            components: list[dict] = job_data.get("components") or []

            types: list[str] = [
                c.get("component_type", "") for c in components if c.get("component_type")
            ]
            runjob_count = sum(1 for t in types if _is_runjob(t))
            has_blockers = any(_is_blocker(t) for t in types)

            score, native_components, blocker_components = _score_job(components)
            qlik_path, qlik_rag, recommendation, migration_tool = _bucket(
                score, has_blockers, runjob_count
            )

            results.append({
                "job_name": job_name,
                "qlik_path": qlik_path,
                "qlik_score": score,
                "qlik_rag": qlik_rag,
                "native_components": native_components,
                "blocker_components": blocker_components,
                "recommendation": recommendation,
                "migration_tool": migration_tool,
            })

        except Exception:
            # Defensive: never let one bad job crash the whole analysis
            job_data_safe: dict = job.get("job_data") or {}
            results.append({
                "job_name": job_data_safe.get("job_name", "Unknown"),
                "qlik_path": "MANUAL_REWRITE",
                "qlik_score": 0,
                "qlik_rag": "RED",
                "native_components": [],
                "blocker_components": [],
                "recommendation": "Full rewrite required — Qlik cannot replace natively",
                "migration_tool": "Manual Rewrite",
            })

    return results
