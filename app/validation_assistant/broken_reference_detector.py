class BrokenReferenceDetector:

    def detect(
        self,
        job_data
    ):

        issues = []

        if not job_data["contexts"]:

            issues.append({

                "issue":
                    "Missing Contexts",

                "severity":
                    "CRITICAL"
            })

        return issues