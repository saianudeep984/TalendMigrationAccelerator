
from app.repository.repository_loader import (
    RepositoryLoader
)

from app.conversion.repository_transformer import (
    RepositoryTransformer
)

from app.validation.import_validator import (
    ImportValidator
)


class BatchConverter:

    # =================================================
    # INITIALIZATION
    # =================================================

    def __init__(self):

        self.loader = RepositoryLoader()

        self.transformer = (
            RepositoryTransformer()
        )

        self.validator = (
            ImportValidator()
        )

    # =================================================
    # PROCESS JOB FILTER
    # =================================================

    def is_process_job(
        self,
        path
    ):

        path = path.replace("\\", "/")

        return (

            "/process/" in path

            and path.endswith(".item")
        )

    # =================================================
    # VALIDATE TALEND REPOSITORY
    # =================================================

    def is_valid_repository(
        self,
        repository
    ):

        errors = []

        has_project = False

        for file in repository["other_files"]:

            if "talend.project" in file["path"]:

                has_project = True

        if not has_project:

            errors.append(
                "Missing talend.project file"
            )

        return errors

    # =================================================
    # MAIN REPOSITORY CONVERSION
    # =================================================

    def convert_repository(
        self,
        zip_bytes
    ):

        # ---------------------------------------------
        # LOAD REPOSITORY
        # ---------------------------------------------

        repository = self.loader.load_repository(
            zip_bytes
        )

        # ---------------------------------------------
        # VALIDATE REPOSITORY STRUCTURE
        # ---------------------------------------------

        validation_errors = (
            self.is_valid_repository(
                repository
            )
        )

        if validation_errors:

            raise Exception(

                "\n".join(validation_errors)
            )

        # ---------------------------------------------
        # VALIDATE IMPORT STRUCTURE
        # ---------------------------------------------

        import_errors = self.validator.validate(
            repository
        )

        if import_errors:

            raise Exception(

                "\n".join(import_errors)
            )

        # ---------------------------------------------
        # FILTER ITEMS
        # ONLY MODIFY PROCESS JOBS
        # ---------------------------------------------

        filtered_repository = {

            "items": [],

            "properties": repository[
                "properties"
            ],

            "other_files": repository[
                "other_files"
            ]
        }

        for item in repository["items"]:

            item_path = item["path"]

            # -----------------------------------------
            # ONLY CONVERT PROCESS JOBS
            # -----------------------------------------

            if self.is_process_job(item_path):

                filtered_repository[
                    "items"
                ].append(item)

            else:

                # -------------------------------------
                # PRESERVE CONTEXTS/Routines EXACTLY
                # -------------------------------------

                filtered_repository[
                    "other_files"
                ].append(item)

        # ---------------------------------------------
        # TRANSFORM REPOSITORY
        # ---------------------------------------------

        converted_zip = (
            self.transformer.transform_repository(
                filtered_repository
            )
        )

        return converted_zip