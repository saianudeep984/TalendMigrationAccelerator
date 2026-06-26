
import io
import zipfile

from app.converters.version_converter import (
    TalendVersionConverter
)

from app.conversion.properties_transformer import (
    PropertiesTransformer
)


class RepositoryTransformer:

    def __init__(self):

        self.item_transformer = (
            TalendVersionConverter()
        )

        self.properties_transformer = (
            PropertiesTransformer()
        )

    # -------------------------------------------------
    # Detect Context Files
    # -------------------------------------------------

    def is_context_item(self, path):

        path = path.lower()

        return (

            "context" in path

            and path.endswith(".item")
        )

    # -------------------------------------------------
    # Transform Repository
    # -------------------------------------------------

    def transform_repository(

        self,
        repository
    ):

        output_buffer = io.BytesIO()

        output_zip = zipfile.ZipFile(

            output_buffer,

            "w",

            zipfile.ZIP_DEFLATED
        )

        # ---------------------------------------------
        # Preserve Context Items EXACTLY
        # ---------------------------------------------

        items       = repository.get("items", []) if repository else []
        properties  = repository.get("properties", []) if repository else []
        other_files = repository.get("other_files", []) if repository else []

        if not items and not properties and not other_files:
            print("Repository export contains no files.")

        for item in items:

            content = item["content"]

            if not content:

                print(
                    f"Skipping empty export file: {item['path']}"
                )

                output_zip.writestr(
                    item["path"],
                    content or ""
                )

                continue

            transformed = content

            try:

                # -------------------------------------
                # DO NOT MODIFY CONTEXT ITEMS
                # -------------------------------------

                if self.is_context_item(

                    item["path"]
                ):

                    transformed = content

                else:

                    transformed = (

                        self.item_transformer.convert(
                            content
                        )
                    )

            except Exception as e:

                print(

                    f"Transformation failed: "
                    f"{str(e)}"
                )

                transformed = content

            output_zip.writestr(

                item["path"],

                transformed
            )

        # ---------------------------------------------
        # Preserve .properties EXACTLY
        # ---------------------------------------------

        for prop in properties:

            prop_content = prop["content"]

            if not prop_content:
                print(
                    f"Skipping empty export file: {prop['path']}"
                )

            output_zip.writestr(

                prop["path"],

                prop_content or ""
            )

        # ---------------------------------------------
        # Preserve Other Files
        # ---------------------------------------------

        for other in other_files:

            other_content = other["content"]

            if not other_content:
                print(
                    f"Skipping empty export file: {other['path']}"
                )

            output_zip.writestr(

                other["path"],

                other_content or ""
            )

        output_zip.close()

        return output_buffer.getvalue()
