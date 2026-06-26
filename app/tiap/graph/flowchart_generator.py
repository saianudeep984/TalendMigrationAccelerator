import os
import struct
import zlib
from typing import Any, Dict, List, Sequence

from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder
from app.tiap.models.repository import iter_job_data, normalize_name


class FlowchartGenerator:
    BUSINESS_LABELS = {
        "tFileInputDelimited": "Customer File",
        "tFileInputExcel": "Excel File",
        "tMap": "Business Rules",
        "tFilterRow": "Validation",
        "tSchemaComplianceCheck": "Schema Validation",
        "tOracleOutput": "Customer Table",
        "tDBOutput": "Target Table",
        "tLogRow": "Audit Output",
    }

    def generate(self, all_jobs: Sequence[Dict[str, Any]], job_name: str = None) -> Dict[str, Any]:
        return {
            "technical_flow": self.technical_flow(all_jobs, job_name),
            "business_flow": self.business_flow(all_jobs, job_name),
            "parent_child_flow": self.parent_child_flow(all_jobs),
            "repository_flow": self.repository_flow(all_jobs),
        }

    def technical_flow(self, all_jobs, job_name=None) -> str:
        components = self._components(all_jobs, job_name)
        return "\n".join(components) if components else "No technical flow detected"

    def business_flow(self, all_jobs, job_name=None) -> str:
        components = self._components(all_jobs, job_name)
        labels = [self.BUSINESS_LABELS.get(component, self._business_name(component)) for component in components]
        return "\n".join(labels) if labels else "No business flow detected"

    def parent_child_flow(self, all_jobs) -> str:
        graph = DependencyGraphBuilder().build(all_jobs)
        lines = [f"{source} -> {target}" for source, target in graph.edges()]
        return "\n".join(lines) if lines else "No parent child dependencies"

    def repository_flow(self, all_jobs) -> str:
        graph = DependencyGraphBuilder().build(all_jobs)
        roots = [n for n in graph.nodes if graph.in_degree(n) == 0]
        return "\n".join(roots or list(graph.nodes)) if graph.nodes else "Empty repository"

    def export(self, flows: Dict[str, str], output_dir: str, basename: str = "flowchart") -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        paths = {}
        svg = self._svg(flows)
        for ext, content in {
            "svg": svg,
            "png": self._png(),
            "pdf": self._pdf(flows),
        }.items():
            path = os.path.join(output_dir, f"{basename}.{ext}")
            mode = "wb" if ext in ("png", "pdf") else "w"
            with open(path, mode, encoding=None if mode == "wb" else "utf-8") as handle:
                data = content.encode("utf-8") if mode == "wb" and isinstance(content, str) else content
                handle.write(data)
            paths[ext] = path
        return paths

    def _components(self, all_jobs, job_name=None) -> List[str]:
        for data in iter_job_data(all_jobs):
            if job_name and normalize_name(data.get("job_name")) != normalize_name(job_name):
                continue
            return [c.get("component_type", "UNKNOWN_COMPONENT") for c in data.get("components", []) if isinstance(c, dict)]
        return []

    def _business_name(self, component: str) -> str:
        text = str(component or "").lstrip("t")
        return " ".join(part for part in text.replace("_", " ").split())

    def _svg(self, flows: Dict[str, str]) -> str:
        rows = flows.get("technical_flow", "").splitlines()[:30]
        height = max(80, len(rows) * 28 + 20)
        text = "".join(f'<text x="20" y="{30 + i * 28}" font-size="14">{row}</text>' for i, row in enumerate(rows))
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}">{text}</svg>'

    def _pdf(self, flows: Dict[str, str]) -> bytes:
        text = "TIAP Flow Export\\n" + "\\n".join(f"{key}: {value}" for key, value in flows.items())
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:3000]
        stream = f"BT /F1 10 Tf 40 780 Td ({safe}) Tj ET"
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream".encode("utf-8"),
        ]
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = []
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{index} 0 obj\n".encode("ascii"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")
        xref = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
        return bytes(pdf)

    def _png(self) -> bytes:
        width, height = 1, 1
        raw = b"\x00\xff\xff\xff"
        def chunk(kind, data):
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
