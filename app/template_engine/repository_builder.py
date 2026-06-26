
import os, shutil

class RepositoryBuilder:

    def build_structure(self, root, template_project=None):
        if template_project and os.path.exists(template_project):
            if os.path.exists(root):
                shutil.rmtree(root, ignore_errors=True)
            shutil.copytree(template_project, root)

            required_folders = [
                'context','metadata','process','code',
                'TDQ_Libraries','Maps','Reports',
                'Structures','Databases','sqlPatterns',
                'documentations'
            ]
            for folder in required_folders:
                os.makedirs(os.path.join(root, folder), exist_ok=True)

            return root

        folders = [
            '.settings','context','metadata/connections',
            'metadata/fileExcel','metadata/fileDelimited',
            'process','code/routines'
        ]
        for folder in folders:
            os.makedirs(os.path.join(root, folder), exist_ok=True)
        return root
