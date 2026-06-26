
import os
import shutil


class IndividualJobExporter:

    def export_jobs(

        self,
        process_dir,
        export_dir
    ):

        os.makedirs(
            export_dir,
            exist_ok=True
        )

        exported = []

        for root, dirs, files in os.walk(

            process_dir

        ):

            for file in files:

                if file.endswith(".item"):

                    source = os.path.join(
                        root,
                        file
                    )

                    dest = os.path.join(
                        export_dir,
                        file
                    )

                    shutil.copy2(
                        source,
                        dest
                    )

                    exported.append(file)

        return exported
