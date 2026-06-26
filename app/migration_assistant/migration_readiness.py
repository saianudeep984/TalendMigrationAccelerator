class MigrationReadiness:

    def evaluate(
        self,
        all_jobs
    ):

        total_jobs = len(all_jobs)

        high_risk = 0

        cloud_blockers = 0

        for job in all_jobs:

            # ---------------------------------
            # Enterprise Risk Report
            # ---------------------------------

            for risk in job[
                "enterprise_risk_report"
            ]:

                if risk["risk"] in [

                    "HIGH",
                    "CRITICAL"
                ]:

                    high_risk += 1

            # ---------------------------------
            # Cloud Readiness
            # ---------------------------------

            readiness = job[
                "cloud_readiness"
            ]["readiness"]

            if readiness == "LOW":

                cloud_blockers += 1

        # -------------------------------------
        # Readiness Score
        # -------------------------------------

        score = max(

            0,

            100 - (
                high_risk * 5
                +
                cloud_blockers * 10
            )
        )

        # -------------------------------------
        # Final Status
        # -------------------------------------

        if score >= 80:

            status = "READY"

        elif score >= 50:

            status = "PARTIAL"

        else:

            status = "HIGH REMEDIATION REQUIRED"

        return {

            "score":
                score,

            "status":
                status,

            "high_risk_components":
                high_risk,

            "cloud_blockers":
                cloud_blockers
        }