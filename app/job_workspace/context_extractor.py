
import os
import shutil


class ContextExtractor:

    def extract_contexts(

        self,
        source_dir,
        target_dir
    ):

        os.makedirs(
            target_dir,
            exist_ok=True
        )

        exported = []

        for root, dirs, files in os.walk(source_dir):

            for file in files:

                if file.endswith(".item") or file.endswith(".properties"):

                    source = os.path.join(
                        root,
                        file
                    )

                    destination = os.path.join(
                        target_dir,
                        file
                    )

                    shutil.copy2(
                        source,
                        destination
                    )

                    exported.append(file)

        return exported
