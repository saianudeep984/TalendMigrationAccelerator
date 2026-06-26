"""
Runtime Validation
Checks migrated jobs for runtime issues.
"""

DEPRECATED_PATTERNS = [
    "tJavaFlex",
    "tELTMap",
    "tPigLoad",
    "tHiveLoad"
]


class RuntimeValidation:

    def validate(
        self,
        all_jobs: list
    ) -> dict:

        issues = []
        passed = []

        for job in all_jobs:

            job_name = job["job_data"].get(
                "job_name", "Unknown"
            )

            components = job["job_data"].get(
                "components", []
            )

            job_issues = []

            for component in components:

                comp_type = component.get(
                    "component_type", ""
                )

                if comp_type in DEPRECATED_PATTERNS:

                    job_issues.append({
                        "component": comp_type,
                        "issue": (
                            f"{comp_type} may fail "
                            "at runtime in Talend 8"
                        ),
                        "severity": "HIGH"
                    })

            if job_issues:
                issues.append({
                    "job": job_name,
                    "issues": job_issues
                })
            else:
                passed.append(job_name)

        return {
            "jobs_with_issues": issues,
            "jobs_passed": passed,
            "total_issues": sum(
                len(j["issues"]) for j in issues
            ),
            "runtime_ready": len(issues) == 0
        }
