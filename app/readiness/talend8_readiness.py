"""
Talend 8 Readiness Engine
Evaluates full repository readiness for Talend 8 migration.
"""

from app.readiness.component_compatibility import REMOVED_COMPONENTS


class Talend8Readiness:

    def evaluate(
        self,
        job_data: dict
    ) -> dict:

        blockers = []
        warnings = []

        components = job_data.get(
            "components", []
        )

        for component in components:

            comp_type = component.get(
                "component_type", ""
            )

            if comp_type in REMOVED_COMPONENTS:

                blockers.append({
                    "component": comp_type,
                    "severity": "CRITICAL",
                    "reason": (
                        f"{comp_type} was removed in Talend 8. "
                        "Must be replaced before migration."
                    )
                })

        # --- Score ---
        if len(blockers) == 0:
            score = 100
            status = "✅ READY"
        elif len(blockers) <= 2:
            score = 50
            status = "⚠️ NEEDS REMEDIATION"
        else:
            score = 10
            status = "❌ BLOCKED"

        return {
            "job_name": job_data.get(
                "job_name", "Unknown"
            ),
            "blockers": blockers,
            "warnings": warnings,
            "blocker_count": len(blockers),
            "readiness_score": score,
            "status": status
        }

    def evaluate_repository(
        self,
        all_jobs: list
    ) -> dict:

        all_results = []
        total_blockers = 0

        for job in all_jobs:

            job_data = job.get("job_data", {})

            result = self.evaluate(job_data)

            all_results.append(result)

            total_blockers += result["blocker_count"]

        overall_score = (
            100 if total_blockers == 0
            else max(0, 100 - total_blockers * 10)
        )

        return {
            "job_results": all_results,
            "total_blockers": total_blockers,
            "overall_score": overall_score,
            "overall_status": (
                "✅ READY" if overall_score >= 80
                else "⚠️ PARTIAL"
                if overall_score >= 40
                else "❌ BLOCKED"
            )
        }
