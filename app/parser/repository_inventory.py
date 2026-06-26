class RepositoryInventory:

    def generate(self, all_jobs):

        inventory = {

            "jobs": 0,

            "components": {},

            "contexts": 0,

            "routines": 0
        }

        for job in all_jobs:

            inventory["jobs"] += 1

            for component in job[
                "job_data"
            ]["components"]:

                ctype = component[
                    "component_type"
                ]

                inventory["components"][
                    ctype
                ] = (

                    inventory["components"]
                    .get(ctype, 0) + 1
                )

        return inventory