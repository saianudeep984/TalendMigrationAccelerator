CLOUD_PATTERNS = {

    "unsupported_cloud_components": [

        "tSystem",
        "tShell",
        "tJava",
        "tRunJob"
    ],

    "recommended_cloud_components": {

        "tFTPGet":
            "tFTPFileList",

        "tMap":
            "Talend Cloud Mapping",

        "tFileInputDelimited":
            "Cloud File Connector"
    },

    "cloud_best_practices": [

        "Avoid local file system usage",

        "Minimize custom Java code",

        "Use Talend Cloud orchestration",

        "Prefer cloud-native connectors"
    ]
}