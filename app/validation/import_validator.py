class ImportValidator:

    def validate(
        self,
        repository
    ):

        errors = []

        # -------------------------------------
        # Validate talend.project
        # -------------------------------------

        has_project = False

        for file in repository["other_files"]:

            if "talend.project" in file["path"]:

                has_project = True

        if not has_project:

            errors.append(

                "Missing talend.project"
            )

        # -------------------------------------
        # Validate Matching Pairs
        # -------------------------------------

        item_names = set()

        property_names = set()

        for item in repository["items"]:

            name = item["path"]

            item_names.add(

                name.replace(".item", "")
            )

        for prop in repository["properties"]:

            name = prop["path"]

            property_names.add(

                name.replace(".properties", "")
            )

        missing = item_names - property_names

        for item in missing:

            errors.append(

                f"Missing .properties for {item}"
            )

        return errors