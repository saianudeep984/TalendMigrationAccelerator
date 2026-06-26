"""
MigrationReportRunner — invokes Talend's migrationreport CLI command.

Fixed from original: same shell=False / list-based args fix.
"""

from app.talend_cli.talend_command_executor import TalendCommandExecutor


class MigrationReportRunner:

    def __init__(self):
        self.executor = TalendCommandExecutor()

    def run(self, talend_studio_path: str, workspace: str) -> dict:
        command = [
            talend_studio_path,
            "-nosplash",
            "-application", "org.talend.commandline.CommandLine",
            "-data", workspace,
            "migrationreport",
        ]
        return self.executor.execute(command)
