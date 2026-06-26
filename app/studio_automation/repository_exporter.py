"""
Repository Exporter — exports the migrated workspace as a ZIP.
"""

import os
import shutil


class RepositoryExporter:

    def export_repository(self, migrated_workspace, export_zip):
        """
        Package the migrated workspace into a ZIP file.
        """
        if not os.path.exists(migrated_workspace):
            raise FileNotFoundError(
                f"Workspace not found: {migrated_workspace}"
            )

        base = export_zip.replace(".zip", "")
        shutil.make_archive(base, "zip", migrated_workspace)

        return export_zip
