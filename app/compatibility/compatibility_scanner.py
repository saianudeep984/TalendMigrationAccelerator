from app.config.version_matrix import (
    VERSION_UPGRADE_MATRIX
)


class CompatibilityScanner:

    def scan(self, job_data):

        issues = []

        rules = VERSION_UPGRADE_MATRIX[
            "7_to_8"
        ]

        removed = rules[
            "removed_components"
        ]

        deprecated = rules[
            "deprecated_components"
        ]

        for component in job_data[
            "components"
        ]:

            ctype = component[
                "component_type"
            ]

            if ctype in removed:

                issues.append({

                    "component": ctype,

                    "severity": "CRITICAL",

                    "issue":
                        "Removed in Talend 8"
                })

            elif ctype in deprecated:

                issues.append({

                    "component": ctype,

                    "severity": "HIGH",

                    "issue":
                        "Deprecated component"
                })

        return issues