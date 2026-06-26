
import os


class WorkspaceBootstrapper:

    def initialize(

        self,
        workspace_path
    ):

        os.makedirs(
            workspace_path,
            exist_ok=True
        )

        folders = [

            ".metadata",
            "projects",
            "logs",
            "migration_reports"
        ]

        for folder in folders:

            os.makedirs(

                os.path.join(
                    workspace_path,
                    folder
                ),

                exist_ok=True
            )

        return workspace_path
