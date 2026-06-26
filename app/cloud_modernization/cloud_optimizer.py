"""
Cloud Optimizer
Generates Talend Cloud / cloud-native optimization recommendations.
"""

CLOUD_NATIVE_REPLACEMENTS = {
    "tFileInputDelimited": "Azure Blob / S3 Input",
    "tFileOutputDelimited": "Azure Blob / S3 Output",
    "tMSSqlInput": "Azure SQL / Synapse Input",
    "tMSSqlOutput": "Azure SQL / Synapse Output",
    "tOracleInput": "Cloud Data Warehouse Input",
    "tOracleOutput": "Cloud Data Warehouse Output",
    "tFTPGet": "Cloud Storage Transfer",
    "tFTPPut": "Cloud Storage Transfer",
    "tSendMail": "Cloud Notification Service",
    "tLogRow": "Cloud Logging / Monitor",
}


class CloudOptimizer:

    def optimize(
        self,
        all_jobs: list
    ) -> dict:

        recommendations = []
        cloud_ready_jobs = []
        needs_work_jobs = []

        for job in all_jobs:

            job_name = job["job_data"].get(
                "job_name", "Unknown"
            )

            components = job["job_data"].get(
                "components", []
            )

            job_recs = []

            for component in components:

                comp_type = component.get(
                    "component_type", ""
                )

                if comp_type in CLOUD_NATIVE_REPLACEMENTS:

                    job_recs.append({
                        "component": comp_type,
                        "cloud_replacement": (
                            CLOUD_NATIVE_REPLACEMENTS[
                                comp_type
                            ]
                        ),
                        "benefit": (
                            "Improved scalability, "
                            "reduced maintenance"
                        )
                    })

            if job_recs:

                needs_work_jobs.append(job_name)

                recommendations.append({
                    "job": job_name,
                    "recommendations": job_recs,
                    "count": len(job_recs)
                })

            else:

                cloud_ready_jobs.append(job_name)

        return {
            "job_recommendations": recommendations,
            "cloud_ready_jobs": cloud_ready_jobs,
            "needs_optimization": needs_work_jobs,
            "total_recommendations": sum(
                r["count"] for r in recommendations
            ),
            "cloud_readiness_pct": (
                round(
                    len(cloud_ready_jobs) /
                    max(len(all_jobs), 1) * 100,
                    1
                )
            )
        }
