
import os

REQUIRED_ITEMS = [
    '.project',
    'talend.project',
    '.settings'
]

class ProjectValidator:

    def validate(self, project_root):
        missing=[]
        for item in REQUIRED_ITEMS:
            if not os.path.exists(os.path.join(project_root,item)):
                missing.append(item)
        return {
            'valid': len(missing)==0,
            'missing': missing
        }
