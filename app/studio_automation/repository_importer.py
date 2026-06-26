
import os

from app.utils.zip_extractor import safe_extract


class RepositoryImporter:

    def import_repository(

        self,
        repository_zip,
        workspace
    ):

        project_dir = os.path.join(
            workspace,
            "imported_repository"
        )

        os.makedirs(
            project_dir,
            exist_ok=True
        )

        safe_extract(repository_zip, project_dir)

        return project_dir
