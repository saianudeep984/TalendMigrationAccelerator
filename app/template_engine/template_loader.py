from pathlib import Path

class TemplateLoader:

    def load_template(self, template_root):
        root = Path(template_root)

        result = {
            "template_root": str(root),
            "contexts": [],
            "connections": [],
            "excel_metadata": [],
            "jobs": [],
            "routines": []
        }

        for file in root.rglob("*"):
            p = str(file)

            if "context" in p and file.suffix in [".item",".properties"]:
                result["contexts"].append(p)

            if "connections" in p and file.suffix in [".item",".properties"]:
                result["connections"].append(p)

            if "fileExcel" in p and file.suffix in [".item",".properties"]:
                result["excel_metadata"].append(p)

            if "process" in p and file.suffix in [".item",".properties"]:
                result["jobs"].append(p)

            if "code" in p and file.suffix in [".item",".properties"]:
                result["routines"].append(p)

        return result
