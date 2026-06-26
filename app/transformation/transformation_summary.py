class TransformationSummary:

    def summarize(
        self,
        transformations
    ):

        summary = {

            "total_changes":
                len(transformations),

            "high_risk": 0
        }

        for item in transformations:

            if item["severity"] == "HIGH":

                summary["high_risk"] += 1

        return summary