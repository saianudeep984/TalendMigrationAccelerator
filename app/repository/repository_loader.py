import os
import zipfile
import io

from app.utils.zip_extractor import _is_unsafe_member

DEFAULT_MAX_ZIP_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


class RepositoryLoader:

    def __init__(self, max_zip_size_bytes=None):
        self.max_zip_size_bytes = (
            max_zip_size_bytes
            if max_zip_size_bytes is not None
            else int(os.environ.get("REPOSITORY_ZIP_MAX_SIZE_BYTES", DEFAULT_MAX_ZIP_SIZE_BYTES))
        )

    def load_repository(
        self,
        zip_bytes
    ):

        if len(zip_bytes) > self.max_zip_size_bytes:
            raise ValueError(
                f"Repository ZIP size ({len(zip_bytes)} bytes) exceeds the configured "
                f"limit ({self.max_zip_size_bytes} bytes)."
            )

        zip_file = zipfile.ZipFile(
            io.BytesIO(zip_bytes)
        )

        total_uncompressed = sum(info.file_size for info in zip_file.infolist())
        if total_uncompressed > self.max_zip_size_bytes:
            raise ValueError(
                f"Repository ZIP uncompressed size ({total_uncompressed} bytes) exceeds "
                f"the configured limit ({self.max_zip_size_bytes} bytes)."
            )

        repository = {

            "items": [],

            "properties": [],

            "other_files": []
        }

        for file in zip_file.namelist():

            if _is_unsafe_member(file):
                raise ValueError(f"Unsafe ZIP member path: {file}")

            content = zip_file.read(file)

            if file.endswith(".item"):

                repository["items"].append({

                    "path": file,

                    "content": content
                })

            elif file.endswith(".properties"):

                repository["properties"].append({

                    "path": file,

                    "content": content
                })

            else:

                repository["other_files"].append({

                    "path": file,

                    "content": content
                })

        return repository