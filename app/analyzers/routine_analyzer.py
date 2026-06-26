"""
Custom Routine Analyzer
Detects Java routines used across the repository and assesses cloud/migration risk.
"""

import os
from collections import defaultdict

from app.tiap.profiling.routine_profiler import RoutineProfiler


# Java patterns that signal risk
_FILE_ACCESS = ["new File(", "FileInputStream", "FileOutputStream", "Files.read",
                "Files.write", "BufferedReader", "FileReader", "FileWriter"]
_RUNTIME_RISK = ["Runtime.getRuntime", "ProcessBuilder", "System.exec",
                 "Class.forName", "ClassLoader"]
_CLOUD_RISK   = _FILE_ACCESS + _RUNTIME_RISK + ["System.getenv", "System.getProperty"]


def _count_lines(text: str) -> int:
    return len([l for l in text.splitlines() if l.strip()])


def _detect_risks(source: str) -> list[str]:
    found = []
    for pattern in _FILE_ACCESS:
        if pattern in source:
            found.append("File System Access")
            break
    for pattern in _RUNTIME_RISK:
        if pattern in source:
            found.append("Runtime Dependency")
            break
    if "System.getenv" in source or "System.getProperty" in source:
        found.append("Environment Variable Access")
    return list(set(found))


def _risk_level(risks: list[str]) -> str:
    if not risks:
        return "LOW"
    if "Runtime Dependency" in risks:
        return "HIGH"
    if "File System Access" in risks:
        return "HIGH"
    return "MEDIUM"


def analyze_routines(all_jobs, repo_path: str = None) -> dict:
    """
    Two-pass analysis:
    1. Scan repo_path/routines/ for .java/.item files to get source code.
    2. Scan all_jobs to find which jobs use each routine (via tJava/tJavaRow/tJavaFlex
       component param or context references).

    Returns:
        {
          "routines": [ {name, lines_of_code, risks, risk_level, cloud_compatible,
                         jobs_using, job_count} ],
          "total_routines": int,
          "high_risk_count": int,
          "total_jobs_impacted": int,
        }
    """

    tiap_profile = RoutineProfiler().profile(all_jobs, repo_path)
    if tiap_profile.get("routine_usage"):
        routines = []
        impacted = set()
        for row in tiap_profile["routine_usage"]:
            jobs_using = [
                job["job_data"]["job_name"]
                for job in all_jobs
                if row["routine"] in str(job.get("job_data", {}).get("components", ""))
            ]
            if row.get("referenced") and not jobs_using:
                jobs_using = ["Referenced in repository metadata"]
            impacted.update(jobs_using)
            routines.append({
                "name": row["routine"],
                "lines_of_code": None,
                "risks": row.get("cloud_risks") or ["None detected"],
                "risk_level": row.get("risk", "LOW"),
                "cloud_compatible": "No" if row.get("risk") == "HIGH" else "Partial" if row.get("risk") == "MEDIUM" else "Yes",
                "jobs_using": jobs_using,
                "job_count": len(jobs_using),
            })
        return {
            "routines": routines,
            "total_routines": len(routines),
            "high_risk_count": sum(1 for row in routines if row["risk_level"] == "HIGH"),
            "total_jobs_impacted": len(impacted),
        }

    # --- Pass 1: collect routine sources ---
    routine_sources = {}   # routine_name -> source_text

    if repo_path and os.path.isdir(repo_path):
        for root, dirs, files in os.walk(repo_path):
            # Look inside any folder named routines
            if "routines" in root.lower() or "routine" in root.lower():
                for fname in files:
                    if fname.endswith((".java", ".item")):
                        routine_name = fname.replace(".java", "").replace(".item", "")
                        # strip version suffix  e.g. MyRoutine_0.1 → MyRoutine
                        if "_" in routine_name:
                            parts = routine_name.rsplit("_", 1)
                            if parts[-1].replace(".", "").isdigit():
                                routine_name = parts[0]
                        try:
                            with open(os.path.join(root, fname), "r",
                                      encoding="utf-8", errors="ignore") as fh:
                                routine_sources[routine_name] = fh.read()
                        except Exception:
                            routine_sources.setdefault(routine_name, "")

    # --- Pass 2: map routine names → jobs ---
    routine_jobs = defaultdict(set)   # routine_name -> set of job_names

    for job in all_jobs:
        jname = job["job_data"]["job_name"]
        # Heuristic: check component names and ai_recommendation text for routine references
        for comp in job["job_data"].get("components", []):
            ctype = comp.get("component_type", "")
            cname = comp.get("name", "")
            # If routine name appears in component instance name
            for rname in routine_sources:
                if rname.lower() in cname.lower():
                    routine_jobs[rname].add(jname)
            # tJava family always counts as using "inline Java"
            if ctype in ("tJava", "tJavaRow", "tJavaFlex"):
                routine_jobs.setdefault("__inline_java__", set()).add(jname)

        # Also scan AI recommendation text for routine mentions
        rec = job.get("ai_recommendation", "")
        for rname in routine_sources:
            if rname in rec:
                routine_jobs[rname].add(jname)

    # --- Build result rows ---
    routines = []

    for rname, source in sorted(routine_sources.items()):
        loc    = _count_lines(source)
        risks  = _detect_risks(source)
        risk   = _risk_level(risks)
        jobs   = sorted(routine_jobs.get(rname, set()))
        cloud  = "No" if risk == "HIGH" else "Partial" if risk == "MEDIUM" else "Yes"
        routines.append({
            "name":            rname,
            "lines_of_code":   loc,
            "risks":           risks if risks else ["None detected"],
            "risk_level":      risk,
            "cloud_compatible": cloud,
            "jobs_using":      jobs,
            "job_count":       len(jobs),
        })

    # Add inline-java synthetic entry if found
    inline_jobs = sorted(routine_jobs.get("__inline_java__", set()))
    if inline_jobs:
        routines.append({
            "name":            "Inline Java (tJava/tJavaRow/tJavaFlex)",
            "lines_of_code":   0,
            "risks":           ["Custom inline Java — requires manual review"],
            "risk_level":      "HIGH",
            "cloud_compatible": "No",
            "jobs_using":      inline_jobs,
            "job_count":       len(inline_jobs),
        })

    # Sort by risk then job count
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    routines.sort(key=lambda r: (order.get(r["risk_level"], 3), -r["job_count"]))

    all_impacted = set()
    for r in routines:
        all_impacted.update(r["jobs_using"])

    return {
        "routines":            routines,
        "total_routines":      len(routines),
        "high_risk_count":     sum(1 for r in routines if r["risk_level"] == "HIGH"),
        "total_jobs_impacted": len(all_impacted),
    }
