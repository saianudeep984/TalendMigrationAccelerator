class JobRuntimeChecker:

    def analyze(self, job_data):

        runtime_risks = []

        for component in job_data[
            "components"
        ]:

            ctype = component[
                "component_type"
            ]

            if ctype == "tJava":

                runtime_risks.append({

                    "risk":
                        "Custom Java Code",

                    "severity":
                        "HIGH"
                })

        return runtime_risks