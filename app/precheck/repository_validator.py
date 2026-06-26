class RepositoryValidator:

    def validate(
        self,
        repository_files
    ):

        required = [

            "talend.project"
        ]

        errors = []

        for item in required:

            exists = any(

                item in f

                for f in repository_files
            )

            if not exists:

                errors.append(

                    f"Missing {item}"
                )

        return errors