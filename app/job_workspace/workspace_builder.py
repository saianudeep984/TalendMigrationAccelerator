
import os


class WorkspaceBuilder:

    def build(

        self,
        workspace_dir
    ):

        folders = [

            "jobs",
            "routines",
            "contexts",
            "metadata",
            "sql",
            "reports"
        ]

        for folder in folders:

            os.makedirs(

                os.path.join(
                    workspace_dir,
                    folder
                ),

                exist_ok=True
            )

        return workspace_dir
