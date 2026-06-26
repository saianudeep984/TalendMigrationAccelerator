VERSION_UPGRADE_MATRIX = {

    "7_to_8": {

        "renamed_components": {

            "tFTPGet": "tFTPFileList",
            "tFTPPut": "tFTPUpload",
            "tSQLRow": "tDBRow"
        },

        "removed_components": [

            "tJavaFlex",
            "tPigLoad",
            "tPigStoreResult",
            "tHiveLoad"
        ],

        "parameter_changes": {

            "tDBInput": {

                "OLD_PARAM": "USE_CURSOR",
                "NEW_PARAM": "FETCH_SIZE"
            }
        },

        "new_required_parameters": {

            "tDBOutput": [

                "TRUNCATE_TABLE"
            ]
        }
    }
}