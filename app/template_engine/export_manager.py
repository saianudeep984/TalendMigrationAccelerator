
from pathlib import Path

class ExportManager:

    def export_html(self, docx_file, output_html):
        Path(output_html).write_text(
            "<html><body><h1>Generated From Template Engine</h1></body></html>",
            encoding="utf-8"
        )

    def export_pdf(self, docx_file, output_pdf):
        Path(output_pdf).touch()
