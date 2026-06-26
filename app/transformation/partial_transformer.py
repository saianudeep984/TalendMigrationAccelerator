class PartialTransformer:

    def transform(
        self,
        job_data
    ):

        transformations = []

        for component in job_data[
            "components"
        ]:

            ctype = component[
                "component_type"
            ]

            # ---------------------------------
            # Example Transformations
            # ---------------------------------

            if ctype == "tFTPGet":

                transformations.append({

                    "component":
                        ctype,

                    "replacement":
                        "tFTPFileList",

                    "severity":
                        "MEDIUM"
                })

            elif ctype == "tJava":

                transformations.append({

                    "component":
                        ctype,

                    "replacement":
                        "Manual Rewrite Required",

                    "severity":
                        "HIGH"
                })

        return transformations