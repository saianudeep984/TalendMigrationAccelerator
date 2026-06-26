"""
RuntimeValidator — post-migration job sanity checker.

Original was a stub returning empty results. This implementation:
  - Checks that every job has at least one component (not empty after migration)
  - Checks for broken context variable references (context vars used in
    components but not declared in any context group)
  - Checks for high-risk deprecated components still present post-migration
  - Checks for missing routine references (routine used but not found in repo)
  - Returns a structured validation report with per-job findings

Used by the Migration Assistant "After" tab.
"""

_DEPRECATED_COMPONENTS = {
    "tELTMap", "tELTMSSqlMap", "tELTOracleMap", "tELTTeradataMap",
    "tHMap", "tSalesforceWave", "tStatCatcher", "tFlowMeter",
    "tRecollect", "tMemorizeRows",
}


class RuntimeValidator:

    def validate(self, repository: list) -> dict:
        """
        Parameters
        ----------
        repository : list
            The all_jobs list from the analysis pipeline. Each entry
            has at minimum a 'job_data' dict with 'job_name',
            'components', and optionally 'context_vars' and 'routines'.

        Returns
        -------
        {
          "status": "pass" | "warn" | "fail",
          "total_jobs": int,
          "passed": int,
          "warnings": int,
          "failures": int,
          "failed_jobs": [ {job_name, issues: [str]} ],
          "warning_jobs": [ {job_name, issues: [str]} ],
          "summary": str,
        }
        """
        if not repository:
            return {
                "status": "pass",
                "total_jobs": 0,
                "passed": 0,
                "warnings": 0,
                "failures": 0,
                "failed_jobs": [],
                "warning_jobs": [],
                "summary": "No jobs to validate.",
            }

        failed_jobs = []
        warning_jobs = []

        for entry in repository:
            job_data = entry.get("job_data", {})
            job_name = job_data.get("job_name", "UNKNOWN")
            components = job_data.get("components", [])
            context_vars = set(job_data.get("context_vars", []))
            routines = set(job_data.get("routines", []))

            errors = []
            warns = []

            # 1. Empty job
            if not components:
                errors.append("Job has 0 components — likely failed to migrate correctly.")

            # 2. Deprecated components still present
            deprecated_found = []
            for comp in components:
                comp_type = comp if isinstance(comp, str) else comp.get("type", "")
                if comp_type in _DEPRECATED_COMPONENTS:
                    deprecated_found.append(comp_type)
            if deprecated_found:
                warns.append(
                    f"Deprecated component(s) still present: {', '.join(set(deprecated_found))}. "
                    "These may not execute in Talend 8."
                )

            # 3. Context variable usage vs declared vars
            # (only possible when job_data carries context_usage info)
            used_vars = set(job_data.get("context_usage", []))
            if used_vars and context_vars:
                missing_vars = used_vars - context_vars
                if missing_vars:
                    errors.append(
                        f"Context variables used but not declared: {', '.join(sorted(missing_vars))}. "
                        "EMF context linking may have failed during Studio import."
                    )

            # 4. Routine references
            used_routines = set(job_data.get("routine_usage", []))
            if used_routines and routines:
                missing_routines = used_routines - routines
                if missing_routines:
                    warns.append(
                        f"Routines referenced but not found in repo: {', '.join(sorted(missing_routines))}."
                    )

            if errors:
                failed_jobs.append({"job_name": job_name, "issues": errors + warns})
            elif warns:
                warning_jobs.append({"job_name": job_name, "issues": warns})

        total = len(repository)
        n_fail = len(failed_jobs)
        n_warn = len(warning_jobs)
        n_pass = total - n_fail - n_warn

        if n_fail > 0:
            status = "fail"
        elif n_warn > 0:
            status = "warn"
        else:
            status = "pass"

        summary = (
            f"{n_pass} jobs passed, {n_warn} with warnings, {n_fail} failed "
            f"out of {total} total."
        )

        return {
            "status": status,
            "total_jobs": total,
            "passed": n_pass,
            "warnings": n_warn,
            "failures": n_fail,
            "failed_jobs": failed_jobs,
            "warning_jobs": warning_jobs,
            "summary": summary,
        }
