import re

# ── Java code-content risk patterns (mirrors java_logic_analyzer) ──────────────
_JAVA_CRITICAL_PATTERNS = [
    r"\bRuntime\.getRuntime\b",
    r"\bProcessBuilder\b",
    r"\bClass\.forName\b",
    r"\bClassLoader\b",
]
_JAVA_HIGH_PATTERNS = [
    r"\b(File|FileInputStream|FileOutputStream|Files\.|BufferedReader|PrintWriter|FileReader|FileWriter)\b",
    r"\bSystem\.(getenv|getProperty|setProperty)\b",
]
_JAVA_MEDIUM_PATTERNS = [
    r"\b(DriverManager|Connection|PreparedStatement|ResultSet|Statement)\b",
]

_JAVA_COMPONENT_TYPES = {"tJava", "tJavaRow", "tJavaFlex"}

_CODE_KEYS = ("CODE", "EXPRESSION", "BODY", "PRECODE", "POSTCODE",
              "JAVA_CODE", "EXPRESSION_CODE", "END_CODE", "START_CODE")


def _extract_java_code(component: dict) -> str:
    params = component.get("parameters") or {}
    parts = [str(params[k]) for k in _CODE_KEYS if params.get(k)]
    if not parts:
        for v in params.values():
            s = str(v or "")
            if len(s) > 20 and any(kw in s for kw in ("=", ";", "{", "}")):
                parts.append(s)
    return "\n".join(parts)


def _java_task_penalty(component: dict) -> int:
    """
    Return a cloud-readiness penalty (0–40) for a single tJava/tJavaRow/tJavaFlex
    component, based on what the embedded Java code actually does.

    Penalty tiers
    -------------
    CRITICAL patterns (Runtime.exec, ProcessBuilder, ClassLoader …) : +40
    HIGH patterns     (File I/O, System.getenv/Property …)           : +20
    MEDIUM patterns   (direct JDBC …)                                : +10
    No cloud-incompatible patterns detected                          :  +5
      (tJava still warrants a small review penalty even when benign)
    """
    code = _extract_java_code(component)
    if not code:
        return 5  # present but no extractable code → minimal review penalty

    if any(re.search(p, code) for p in _JAVA_CRITICAL_PATTERNS):
        return 40
    if any(re.search(p, code) for p in _JAVA_HIGH_PATTERNS):
        return 20
    if any(re.search(p, code) for p in _JAVA_MEDIUM_PATTERNS):
        return 10
    return 5  # pure logic (string ops, math, date, collections …) — low cloud risk


_SEVERITY_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

_FIXED_SEVERITY = {
    "tSystem":      "CRITICAL",  # hard blocker — OS-level call, never cloud-safe
    "tLibraryLoad": "HIGH",      # custom JAR loader — container-incompatible
    "tRunJob":      "MEDIUM",    # inter-job coupling — complicates cloud deployment
}


def calculate_cloud_readiness(job_data: dict) -> dict:
    """
    Determine Cloud Readiness for a single job as a RED/AMBER/GREEN rating.

    No numeric score is computed. Instead, the worst severity tier found
    across all components determines the rating directly.

    Severity sources
    -----------------
    tSystem        : CRITICAL (hard blocker)
    tLibraryLoad   : HIGH
    tRunJob        : MEDIUM
    tJava family   : LOW–CRITICAL (risk-weighted by code content; see _java_task_penalty)

    Rating rule (worst severity found → rating)
    ---------------------------------------------
    CRITICAL          → readiness LOW    → rag RED
    HIGH              → readiness MEDIUM → rag AMBER
    MEDIUM/LOW/NONE   → readiness HIGH   → rag GREEN

    Returns
    -------
    {
        "readiness": "HIGH" | "MEDIUM" | "LOW",
        "rag": "RED" | "AMBER" | "GREEN",
        "java_task_findings": [{"component": str, "penalty": int, "risk_tier": str}]
    }
    """
    java_task_findings = []
    worst = "NONE"

    for component in job_data.get("components", []):
        comp_type = component.get("component_type", "")

        if comp_type in _FIXED_SEVERITY:
            sev = _FIXED_SEVERITY[comp_type]
            if _SEVERITY_RANK[sev] > _SEVERITY_RANK[worst]:
                worst = sev

        elif comp_type in _JAVA_COMPONENT_TYPES:
            penalty = _java_task_penalty(component)

            if penalty >= 40:
                risk_tier = "CRITICAL"
            elif penalty >= 20:
                risk_tier = "HIGH"
            elif penalty >= 10:
                risk_tier = "MEDIUM"
            else:
                risk_tier = "LOW"

            if _SEVERITY_RANK[risk_tier] > _SEVERITY_RANK[worst]:
                worst = risk_tier

            java_task_findings.append({
                "component": component.get("unique_name", comp_type),
                "component_type": comp_type,
                "penalty": penalty,
                "risk_tier": risk_tier,
            })

    if worst == "CRITICAL":
        readiness, rag = "LOW", "RED"
    elif worst == "HIGH":
        readiness, rag = "MEDIUM", "AMBER"
    else:  # MEDIUM, LOW, or NONE
        readiness, rag = "HIGH", "GREEN"

    return {
        "readiness": readiness,
        "rag": rag,
        "java_task_findings": java_task_findings,
    }


# ── Repository-level cloud readiness (canonical) ───────────────────────────────
# Previously duplicated verbatim in app.tiap.assessment.cloud_readiness and
# app.analyzers.readiness_scorer; both now import this single definition.

class CloudReadinessAnalyzer:
    BLOCKERS = {"tSystem", "tLibraryLoad", "tJavaFlex", "tBeanShell"}
    REVIEW = {"tJava", "tJavaRow", "tFileInputDelimited", "tFileOutputDelimited"}

    def analyze(self, all_jobs) -> dict:
        blockers, review = [], []
        total_components = 0
        for job in all_jobs:
            job_name = job.get("job_data", {}).get("job_name", "Unknown")
            for component in job.get("job_data", {}).get("components", []):
                ctype = component.get("component_type", "")
                total_components += 1
                if ctype in self.BLOCKERS:
                    blockers.append({"job": job_name, "component": ctype})
                elif ctype in self.REVIEW:
                    review.append({"job": job_name, "component": ctype})
        penalty = len(blockers) * 12 + len(review) * 3
        score = max(0, 100 - min(100, penalty))
        return {
            "cloud_readiness_score": score,
            "readiness": "HIGH" if score >= 75 else "MEDIUM" if score >= 45 else "LOW",
            "cloud_blockers": blockers,
            "cloud_review_items": review,
            "components_scanned": total_components,
        }


class CloudReadinessEngine:
    """Unified façade over per-job and repository-level cloud readiness checks
    (F2.2 unified readiness architecture)."""

    def analyze_job(self, job_data: dict) -> dict:
        return calculate_cloud_readiness(job_data)

    def analyze_repository(self, all_jobs) -> dict:
        return CloudReadinessAnalyzer().analyze(all_jobs)

