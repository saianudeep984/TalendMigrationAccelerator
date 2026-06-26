import shutil
from app.talend_cli.workspace_bootstrapper import WorkspaceBootstrapper
from app.studio_automation.repository_importer import RepositoryImporter
from app.talend_cli.repository_migrator import RepositoryMigrator
from app.utils.workspace_cleanup import WorkspaceCleanup

class FullMigrationOrchestrator:
    def __init__(self):
        self.bootstrapper = WorkspaceBootstrapper()
        self.importer = RepositoryImporter()
        self.migrator = RepositoryMigrator()
        self.cleanup_manager = WorkspaceCleanup()

    def migrate(self, talend_studio_path, repository_zip, workspace_path,
                export_zip=None, cleanup_workspace=False):
        try:
            self.bootstrapper.initialize(workspace_path)
            imported_repo = self.importer.import_repository(repository_zip, workspace_path)
            cli_result = self.migrator.migrate(talend_studio_path, workspace_path)

            generated_zip = export_zip
            if export_zip:
                shutil.copy2(repository_zip, export_zip)
                generated_zip = export_zip

            return {
                "status":"migration_prepared",
                "workspace":workspace_path,
                "repository":imported_repo,
                "cli_result":cli_result,
                "output_zip":generated_zip
            }
        finally:
            if cleanup_workspace:
                self.cleanup_manager.cleanup(workspace_path)
