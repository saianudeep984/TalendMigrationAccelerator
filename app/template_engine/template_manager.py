
from pathlib import Path
import shutil

class TemplateManager:
    def __init__(self, base_dir="templates"):
        self.base = Path(base_dir)
        self.default_template = self.base / "default_template.docx"
        self.custom_dir = self.base / "custom"
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        self.custom_template = self.custom_dir / "uploaded_template.docx"

    def get_active_template(self):
        return self.custom_template if self.custom_template.exists() else self.default_template

    def upload_template(self, source_file):
        shutil.copy2(source_file, self.custom_template)
        return str(self.custom_template)

    def restore_default(self):
        if self.custom_template.exists():
            self.custom_template.unlink()
