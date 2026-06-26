MIGRATION_PATTERNS = {

    "Talend7_to_8": {

        "deprecated_components": [

            "tHiveLoad",
            "tPigLoad",
            "tPigStoreResult"
        ],

        "recommended_platform":
            "Talend 8 Cloud",

        "migration_strategy":
            "Incremental Modernization"
    },

    "OpenStudio_to_Cloud": {

        "recommended_runtime":
            "Remote Engine",

        "cloud_blockers": [

            "tJava",
            "tSystem",
            "tRunJob"
        ],

        "modernization_priority":
            "HIGH"
    }
}