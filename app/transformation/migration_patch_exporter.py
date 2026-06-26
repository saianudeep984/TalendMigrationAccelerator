import json
import os


class MigrationPatchExporter:

    def export(
        self,
        output_dir,
        patches
    ):

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        output_file = os.path.join(

            output_dir,

            "migration_patch.json"
        )

        with open(output_file, "w") as f:

            json.dump(
                patches,
                f,
                indent=4,
                allow_nan=False
            )

        with open(output_file, "r") as f:
            try:
                json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Exported JSON failed validation at {output_file}: {e}"
                ) from e

        return output_file