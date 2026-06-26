"""
Repository Comparator
Compares pre-migration and post-migration repositories.
"""


class RepositoryCompare:

    def compare(
        self,
        pre_jobs: list,
        post_jobs: list
    ) -> dict:

        pre_names = {
            j["job_data"]["job_name"]
            for j in pre_jobs
        }

        post_names = {
            j["job_data"]["job_name"]
            for j in post_jobs
        }

        added = list(post_names - pre_names)
        removed = list(pre_names - post_names)
        common = list(pre_names & post_names)

        component_changes = []

        pre_map = {
            j["job_data"]["job_name"]: j
            for j in pre_jobs
        }

        post_map = {
            j["job_data"]["job_name"]: j
            for j in post_jobs
        }

        for name in common:

            pre_count = len(
                pre_map[name]["job_data"].get(
                    "components", []
                )
            )

            post_count = len(
                post_map[name]["job_data"].get(
                    "components", []
                )
            )

            if pre_count != post_count:

                component_changes.append({
                    "job": name,
                    "pre_components": pre_count,
                    "post_components": post_count,
                    "delta": post_count - pre_count
                })

        return {
            "jobs_added": added,
            "jobs_removed": removed,
            "jobs_in_common": len(common),
            "component_changes": component_changes,
            "pre_job_count": len(pre_jobs),
            "post_job_count": len(post_jobs),
            "migration_complete": len(removed) == 0
        }
