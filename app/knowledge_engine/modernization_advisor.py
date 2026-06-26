from app.knowledge_engine.component_knowledgebase import (
    COMPONENT_KNOWLEDGEBASE
)


class ModernizationAdvisor:

    def analyze(
        self,
        job_data
    ):

        recommendations = []

        for component in job_data[
            "components"
        ]:

            ctype = component[
                "component_type"
            ]

            if ctype in COMPONENT_KNOWLEDGEBASE:

                recommendations.append({

                    "component":
                        ctype,

                    "risk":
                        COMPONENT_KNOWLEDGEBASE[
                            ctype
                        ]["risk"],

                    "modernization":
                        COMPONENT_KNOWLEDGEBASE[
                            ctype
                        ]["modernization"],

                    "replacement":
                        COMPONENT_KNOWLEDGEBASE[
                            ctype
                        ][
                            "recommended_replacement"
                        ]
                })

        return recommendations