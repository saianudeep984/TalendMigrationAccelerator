"""
Joblet Analyzer
Detects joblets in the repository and which jobs reuse them.
A joblet is a reusable sub-job component stored under joblets/ or referenced via tRunJoblet.
"""

import os
from collections import defaultdict

from app.tiap.profiling.joblet_profiler import JobletProfiler


_JOBLET_COMPONENT_TYPES = {"tRunJoblet", "tJoblet", "tSubjob"}


def analyze_joblets(all_jobs, repo_path: str = None) -> dict:
    """
    Returns:
        {
          "joblets": [ {name, source, jobs_using, job_count, impact_score, risk_level} ],
          "total_joblets": int,
          "total_jobs_impacted": int,
        }
    """

    tiap_profile = JobletProfiler().profile(all_jobs)
    if tiap_profile.get("joblet_usage_matrix"):
        joblets = []
        impacted = set()
        for row in tiap_profile["joblet_usage_matrix"]:
            jobs = row.get("jobs_using_it", [])
            impacted.update(jobs)
            joblets.append({
                "name": row["joblet"],
                "source": "TIAP joblet profile",
                "jobs_using": jobs,
                "job_count": len(jobs),
                "impact_score": row.get("impact", 0),
                "risk_level": row.get("migration_risk", "LOW"),
            })
        return {
            "joblets": joblets,
            "total_joblets": len(joblets),
            "total_jobs_impacted": len(impacted),
        }

    joblet_jobs  = defaultdict(set)   # joblet_name -> set of job_names
    known_joblet_names = set()

    # --- Pass 1: discover joblet .item files in repo ---
    if repo_path and os.path.isdir(repo_path):
        for root, dirs, files in os.walk(repo_path):
            if "joblets" in root.lower() or "joblet" in root.lower():
                for fname in files:
                    if fname.endswith(".item"):
                        jname = fname.replace(".item", "")
                        if "_" in jname:
                            parts = jname.rsplit("_", 1)
                            if parts[-1].replace(".", "").isdigit():
                                jname = parts[0]
                        known_joblet_names.add(jname)

    # --- Pass 2: scan jobs for tRunJoblet components ---
    for job in all_jobs:
        jname = job["job_data"]["job_name"]
        for comp in job["job_data"].get("components", []):
            ctype = comp.get("component_type", "")
            cname = comp.get("name", "")
            if ctype in _JOBLET_COMPONENT_TYPES:
                # name might be "MyJoblet_tRunJoblet_1" etc — extract joblet label
                label = cname.split("_")[0] if "_" in cname else cname
                joblet_jobs[label].add(jname)
                known_joblet_names.add(label)

    # --- Build result rows ---
    joblets = []
    all_impacted = set()

    for jlet in sorted(known_joblet_names):
        jobs = sorted(joblet_jobs.get(jlet, set()))
        job_count = len(jobs)
        impact = min(job_count * 10, 100)   # simple impact 0-100

        risk = "HIGH" if job_count >= 10 else "MEDIUM" if job_count >= 3 else "LOW"

        source = "joblets/ folder" if os.path.isdir(
            os.path.join(repo_path or "", "joblets")
        ) else "Detected via tRunJoblet"

        joblets.append({
            "name":        jlet,
            "source":      source,
            "jobs_using":  jobs,
            "job_count":   job_count,
            "impact_score": impact,
            "risk_level":  risk,
        })
        all_impacted.update(jobs)

    # Sort by impact descending
    joblets.sort(key=lambda j: -j["impact_score"])

    return {
        "joblets":             joblets,
        "total_joblets":       len(joblets),
        "total_jobs_impacted": len(all_impacted),
    }
