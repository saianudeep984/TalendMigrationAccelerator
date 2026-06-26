
from app.talend_cli.migrationcheck_runner import (
    MigrationCheckRunner
)

from app.talend_cli.migrationreport_runner import (
    MigrationReportRunner
)


class RepositoryMigrator:

    def __init__(self):

        self.check_runner = (
            MigrationCheckRunner()
        )

        self.report_runner = (
            MigrationReportRunner()
        )

    def migrate(

        self,
        talend_studio_path,
        workspace
    ):

        check_result = (
            self.check_runner.run(
                talend_studio_path,
                workspace
            )
        )

        report_result = (
            self.report_runner.run(
                talend_studio_path,
                workspace
            )
        )

        return {

            "migration_check": check_result,

            "migration_report": report_result
        }
