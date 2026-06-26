COMPONENT_KNOWLEDGEBASE = {

    "tJava": {

        "risk": "HIGH",

        "cloud_support": False,

        "modernization":
            "Rewrite using Talend native components",

        "talend8_support":
            "PARTIAL",

        "recommended_replacement":
            "tMap / Talend Routine",

        "migration_effort":
            "HIGH"
    },

    "tJavaRow": {

        "risk": "HIGH",

        "cloud_support": False,

        "modernization":
            "Replace with tMap expressions",

        "talend8_support":
            "PARTIAL",

        "recommended_replacement":
            "tMap",

        "migration_effort":
            "HIGH"
    },

    "tFTPGet": {

        "risk": "MEDIUM",

        "cloud_support": True,

        "modernization":
            "Replace with secure file transfer",

        "talend8_support":
            "DEPRECATED",

        "recommended_replacement":
            "tFTPFileList",

        "migration_effort":
            "LOW"
    },

    "tRunJob": {

        "risk": "HIGH",

        "cloud_support": False,

        "modernization":
            "Use Talend Cloud orchestration",

        "talend8_support":
            "LIMITED",

        "recommended_replacement":
            "Talend Pipeline",

        "migration_effort":
            "MEDIUM"
    },

    "tHiveLoad": {

        "risk": "CRITICAL",

        "cloud_support": False,

        "modernization":
            "Replace with Spark components",

        "talend8_support":
            "REMOVED",

        "recommended_replacement":
            "tSparkConfiguration",

        "migration_effort":
            "HIGH"
    }
}