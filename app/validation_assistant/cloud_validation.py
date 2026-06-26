class CloudValidation:

    def validate(
        self,
        job_data
    ):

        blockers = []

        for component in job_data[
            "components"
        ]:

            ctype = component[
                "component_type"
            ]

            if ctype in [

                "tRunJob",
                "tJava",
                "tSystem"

            ]:

                blockers.append({

                    "component":
                        ctype,

                    "severity":
                        "HIGH",

                    "issue":
                        "Cloud Migration Risk"
                })

        return blockers