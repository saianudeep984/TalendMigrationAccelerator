
import os
import io

from app.utils.zip_extractor import safe_extract


class RepositorySplitter:

    def split_repository(

        self,
        zip_bytes,
        output_dir
    ):

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        safe_extract(io.BytesIO(zip_bytes), output_dir)

        return {

            "jobs": os.path.join(
                output_dir,
                "process"
            ),

            "contexts": os.path.join(
                output_dir,
                "context"
            ),

            "metadata": os.path.join(
                output_dir,
                "metadata"
            ),

            "routines": os.path.join(
                output_dir,
                "code"
            )
        }
