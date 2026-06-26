"""
MigrationCheckRunner — invokes Talend's migrationcheck CLI command.

Fixed from original:
- Builds a list-based command (no shell=True, no f-string quoting).
- Works correctly on paths that contain spaces on both Windows and POSIX.
"""

from app.talend_cli.talend_command_executor import TalendCommandExecutor


class MigrationCheckRunner:

    def __init__(self):
        self.executor = TalendCommandExecutor()

    def run(self, talend_studio_path: str, workspace: str) -> dict:
        command = [
            talend_studio_path,
            "-nosplash",
            "-application", "org.talend.commandline.CommandLine",
            "-data", workspace,
            "migrationcheck",
        ]
        return self.executor.execute(command)
