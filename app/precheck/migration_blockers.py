"""
Migration Blockers Detector
Detects components and patterns that block Talend 8 migration.
"""

HARD_BLOCKERS = [
    "tPigLoad",
    "tPigStore",
    "tHiveLoad",
    "tHiveInput",
    "tHiveOutput",
    "tHiveRow",
    "tSparkLoad",
    "tJavaFlex",
    "tELTMap",
    "tELTInput",
    "tELTOutput"
]

SOFT_BLOCKERS = [
    "tJava",
    "tJavaRow",
    "tBeanInput",
    "tBeanOutput",
    "tSoap",
    "tWebService"
]


class MigrationBlockers:

    def detect(
        self,
        all_jobs: list
    ) -> dict:

        hard = []
        soft = []
        total_jobs_blocked = 0

        for job in all_jobs:

            job_name = job.get(
                "job_data", {}
            ).get("job_name", "Unknown")

            components = job.get(
                "job_data", {}
            ).get("components", [])

            job_has_hard = False

            for component in components:

                comp_type = component.get(
                    "component_type", ""
                )

                if comp_type in HARD_BLOCKERS:

                    hard.append({
                        "job": job_name,
                        "component": comp_type,
                        "severity": "CRITICAL",
                        "action": (
                            f"Replace {comp_type} — "
                            "not supported in Talend 8"
                        )
                    })

                    job_has_hard = True

                elif comp_type in SOFT_BLOCKERS:

                    soft.append({
                        "job": job_name,
                        "component": comp_type,
                        "severity": "WARNING",
                        "action": (
                            f"Review {comp_type} — "
                            "may need manual adjustment"
                        )
                    })

            if job_has_hard:
                total_jobs_blocked += 1

        return {
            "hard_blockers": hard,
            "soft_blockers": soft,
            "hard_blocker_count": len(hard),
            "soft_blocker_count": len(soft),
            "jobs_critically_blocked": total_jobs_blocked,
            "migration_blocked": len(hard) > 0
        }
