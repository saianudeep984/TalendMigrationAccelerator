class MigrationValidator:

    def validate(
        self,
        source_jobs,
        migrated_jobs
    ):

        report = {

            "missing_jobs": [],

            "changed_jobs": [],

            "valid_jobs": []
        }

        source_names = {

            j["job_data"]["job_name"]

            for j in source_jobs
        }

        migrated_names = {

            j["job_data"]["job_name"]

            for j in migrated_jobs
        }

        for name in source_names:

            if name not in migrated_names:

                report[
                    "missing_jobs"
                ].append(name)

            else:

                report[
                    "valid_jobs"
                ].append(name)

        return report