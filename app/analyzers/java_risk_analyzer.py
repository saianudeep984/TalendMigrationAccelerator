try:
    import streamlit as st
except ImportError:
    import types as _types
    st = _types.SimpleNamespace(
        cache_data=lambda *a, **kw: (lambda fn: fn) if not a else a[0] if callable(a[0]) else (lambda fn: fn),
    )
"""
Java Risk Analyzer
Scans every job for inline Java (tJava / tJavaRow / tJavaFlex) and
custom routines, then generates a repository-level Java Risk Score.
"""

from app.tiap.refactoring.java_refactor import JavaRefactor


_JAVA_COMPONENT_TYPES = {"tJava", "tJavaRow", "tJavaFlex"}

_FILE_RISK_PATTERNS    = ["new File(", "FileInputStream", "FileOutputStream",
                           "FileReader", "FileWriter", "BufferedReader"]
_RUNTIME_RISK_PATTERNS = ["Runtime.getRuntime", "ProcessBuilder", "System.exec",
                           "Class.forName"]
_API_RISK_PATTERNS     = ["sun.misc", "com.sun.", "javax.xml.parsers",
                           "org.apache.log4j", "org.apache.commons"]
_CLOUD_RISK_PATTERNS   = _FILE_RISK_PATTERNS + _RUNTIME_RISK_PATTERNS + [
    "System.getenv", "System.getProperty", "System.setProperty"
]


def _scan_text(text: str) -> dict:
    detected = {
        "file_access":     any(p in text for p in _FILE_RISK_PATTERNS),
        "runtime_exec":    any(p in text for p in _RUNTIME_RISK_PATTERNS),
        "unsupported_api": any(p in text for p in _API_RISK_PATTERNS),
        "cloud_risk":      any(p in text for p in _CLOUD_RISK_PATTERNS),
    }
    return detected


def _component_risk_level(flags: dict) -> str:
    if flags["runtime_exec"]:
        return "CRITICAL"
    if flags["file_access"] or flags["unsupported_api"]:
        return "HIGH"
    if flags["cloud_risk"]:
        return "MEDIUM"
    return "LOW"


@st.cache_data(show_spinner=False)
def analyze_java_risks(_all_jobs) -> dict:
    """
    Returns:
        {
          "job_risks": [ {job_name, java_components, flags, risk_level, score} ],
          "summary": {total_java_jobs, critical, high, medium, low, repo_score},
          "risk_score": int (0-100, higher = more risk)
        }
    """

    refactor = JavaRefactor().analyze(_all_jobs)
    if refactor.get("tjava_analysis"):
        job_risks = []
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for row in refactor["tjava_analysis"]:
            flags = {
                "file_access": row.get("file_operations", False),
                "runtime_exec": False,
                "unsupported_api": False,
                "cloud_risk": row.get("file_operations", False) or row.get("jdbc_calls", False),
            }
            risk = "HIGH" if flags["file_access"] else "MEDIUM" if flags["cloud_risk"] else "LOW"
            score = {"CRITICAL": 100, "HIGH": 75, "MEDIUM": 40, "LOW": 10}[risk]
            counts[risk] += 1
            job_risks.append({
                "job_name": row["job"],
                "java_components": [row["component_type"]],
                "java_count": 1,
                "flags": flags,
                "risk_level": risk,
                "score": score,
            })
        repo_score = int(sum(row["score"] for row in job_risks) / len(job_risks))
        return {
            "job_risks": sorted(job_risks, key=lambda row: -row["score"]),
            "summary": {
                "total_java_jobs": len(job_risks),
                "critical": counts["CRITICAL"],
                "high": counts["HIGH"],
                "medium": counts["MEDIUM"],
                "low": counts["LOW"],
            },
            "risk_score": repo_score,
        }

    job_risks = []
    counts    = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for job in _all_jobs:
        jname  = job["job_data"]["job_name"]
        java_comps = [
            c for c in job["job_data"].get("components", [])
            if c.get("component_type") in _JAVA_COMPONENT_TYPES
        ]

        if not java_comps:
            continue

        # aggregate flags across all java components in this job
        agg_flags = {
            "file_access":     False,
            "runtime_exec":    False,
            "unsupported_api": False,
            "cloud_risk":      False,
        }

        for comp in java_comps:
            # Component name / metadata may carry source snippets; scan name
            text = comp.get("name", "") + " " + comp.get("component_type", "")
            flags = _scan_text(text)
            for k in agg_flags:
                if flags[k]:
                    agg_flags[k] = True

        risk  = _component_risk_level(agg_flags)
        score = {"CRITICAL": 100, "HIGH": 75, "MEDIUM": 40, "LOW": 10}[risk]
        counts[risk] += 1

        job_risks.append({
            "job_name":        jname,
            "java_components": [c["component_type"] for c in java_comps],
            "java_count":      len(java_comps),
            "flags":           agg_flags,
            "risk_level":      risk,
            "score":           score,
        })

    # sort by score desc
    job_risks.sort(key=lambda r: -r["score"])

    total_java_jobs = len(job_risks)
    repo_score = 0
    if total_java_jobs:
        repo_score = int(
            sum(r["score"] for r in job_risks) / total_java_jobs
        )

    return {
        "job_risks":  job_risks,
        "summary": {
            "total_java_jobs": total_java_jobs,
            "critical":        counts["CRITICAL"],
            "high":            counts["HIGH"],
            "medium":          counts["MEDIUM"],
            "low":             counts["LOW"],
        },
        "risk_score": repo_score,
    }
