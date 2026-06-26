class RemediationReport:

    def generate(
        self,
        issues
    ):

        recommendations = []

        for issue in issues:

            recommendations.append({

                "issue":
                    issue,

                "action":
                    "Manual review required"
            })

        return recommendations