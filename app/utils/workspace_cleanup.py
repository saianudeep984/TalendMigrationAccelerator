
import os, shutil
class WorkspaceCleanup:
    def cleanup(self, workspace_path):
        if workspace_path and os.path.exists(workspace_path):
            shutil.rmtree(workspace_path, ignore_errors=True)
            return True
        return False
