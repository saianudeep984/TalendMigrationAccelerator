REMEDIATION_RULES = {

    "tJava": {

        "action":
            "Rewrite custom Java logic",

        "priority":
            "HIGH",

        "recommended_fix":
            "Use Talend native transformations"
    },

    "tRunJob": {

        "action":
            "Replace orchestration pattern",

        "priority":
            "MEDIUM",

        "recommended_fix":
            "Talend Cloud Pipelines"
    },

    "tHiveLoad": {

        "action":
            "Replace deprecated Hive integration",

        "priority":
            "CRITICAL",

        "recommended_fix":
            "Spark / Snowflake connector"
    }
}