
import subprocess
import os


class MigrationExecutor:
    """
    Launches Talend Studio GUI so the user can complete the interactive
    import/migration steps inside the Studio UI.

    This is intentionally a non-blocking launch (Popen) because Studio
    initialisation takes time and the user interacts with it manually.
    The CLI migration commands (migrationcheck / migrationreport) are
    handled separately by RepositoryMigrator / TalendCommandExecutor.
    """

    def execute(self, studio_path, workspace):
        if not os.path.exists(studio_path):
            return {
                "status": "failed",
                "error": f"Studio executable not found: {studio_path}"
            }

        try:
            process = subprocess.Popen(
                [studio_path, "-data", workspace],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {
                "status": "studio_launched",
                "pid": process.pid,
                "workspace": workspace
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
