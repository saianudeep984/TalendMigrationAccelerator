from typing import Any, Dict, Sequence

from app.tiap.documentation.export_utils import export_document, markdown_table
from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder
from app.tiap.inventory.inventory_parser import InventoryParser
from app.parser.source_target_extractor import build_source_target_inventory


DEFAULT_TECHNICAL_DOC_TEMPLATE = """## {job_name}

### Job Understanding
- Purpose: This job moves or transforms data using the detected source, transformation, and target components below.
- Source Systems: {sources}
- Target Systems: {targets}
- Main Flow: {main_flow}

### Job Flow Chart
```mermaid
{job_flowchart}
```

### Component Walkthrough
{component_walkthrough}

### Context And Runtime Configuration
- Contexts: {contexts}
- Metadata: {metadata}
- Routines: {routines}
- Joblets: {joblets}

### Dependencies
- Parent Jobs: {parent_jobs}
- Child Jobs: {child_jobs}

### Error Handling And Operations
- Error Handling: {error_handling}
- Operational Notes: Validate context values, connections, rejected rows, and scheduler/runtime dependencies after import.

### Migration Understanding
- Complexity Score: {complexity_score}
- Review Focus: {review_focus}
"""


class TechnicalDocGenerator:
    def generate(
        self,
        all_jobs: Sequence[Dict[str, Any]],
        repository_path: str = None,
        template: str = None,
    ) -> str:
        inventory = InventoryParser().build_inventory(all_jobs, repository_path)
        dependency = DependencyGraphBuilder().analyze(all_jobs)
        lines = ["# Technical Documentation", ""]
        lines.append(f"Total Jobs: {inventory['kpis'].get('total_jobs', 0)}")
        lines.append(f"Total Components: {inventory['kpis'].get('total_components', 0)}")
        lines.append("")
        for job in inventory.get("jobs", []):
            lines.extend([self._render_job_understanding(job, template), ""])
        lines.append("## Dependency Statistics")
        lines.append(str(dependency.get("dependency_statistics", {})))
        return "\n".join(lines)

    def export(self, all_jobs, output_dir, repository_path=None, template=None):
        return export_document(
            output_dir,
            "technical_documentation",
            "Technical Documentation",
            self.generate(all_jobs, repository_path, template),
        )

    def _error_handling(self, job):
        names = {c.get("component_type") for c in job.get("components", [])}
        handlers = sorted(names & {"tDie", "tWarn", "tLogCatcher", "tAssertCatcher"})
        return ", ".join(handlers) if handlers else "No explicit error handling components detected"

    def _render_job_understanding(self, job, template=None):
        inv = build_source_target_inventory(job)
        components = job.get("components", [])
        component_rows = [
            {"Component": c.get("component_type", ""), "Unique Name": c.get("unique_name", "")}
            for c in components
        ]
        component_types = [c.get("component_type", "") for c in components]
        inputs = [c for c in component_types if "Input" in c or "File" in c]
        outputs = [c for c in component_types if "Output" in c or "Reject" in c]
        transforms = [
            c for c in component_types
            if c not in inputs and c not in outputs
        ]
        review_focus = []
        if any(c in {"tJava", "tJavaRow", "tJavaFlex"} for c in component_types):
            review_focus.append("custom Java compatibility")
        if job.get("child_jobs"):
            review_focus.append("parent-child orchestration")
        if not review_focus:
            review_focus.append("standard import and regression validation")
        values = {
            "job_name": job.get("job_name", "Unknown"),
            "complexity_score": job.get("complexity_score", 0),
            "contexts": ", ".join(job.get("contexts", [])) or "None",
            "joblets": ", ".join(job.get("joblets", [])) or "None",
            "routines": ", ".join(job.get("routines", [])) or "None",
            "metadata": ", ".join(job.get("metadata", [])) or "None",
            "parent_jobs": ", ".join(job.get("parent_jobs", [])) or "None",
            "child_jobs": ", ".join(job.get("child_jobs", [])) or "None",
            "error_handling": self._error_handling(job),
            "sources": ", ".join(inv.get("source_names", [])) or "None detected",
            "targets": ", ".join(inv.get("target_names", [])) or "None detected",
            "main_flow": self._main_flow(inputs, transforms, outputs),
            "job_flowchart": self._job_flowchart(job),
            "component_walkthrough": markdown_table(component_rows, ["Component", "Unique Name"]) or "No components detected",
            "review_focus": ", ".join(review_focus),
        }
        try:
            return (template or DEFAULT_TECHNICAL_DOC_TEMPLATE).format(**values)
        except Exception:
            return DEFAULT_TECHNICAL_DOC_TEMPLATE.format(**values)

    def _main_flow(self, inputs, transforms, outputs):
        steps = []
        if inputs:
            steps.append("read from " + ", ".join(inputs[:5]))
        if transforms:
            steps.append("process through " + ", ".join(transforms[:8]))
        if outputs:
            steps.append("write to " + ", ".join(outputs[:5]))
        return " -> ".join(steps) if steps else "No clear component flow detected"

    def _job_flowchart(self, job):
        components = [c for c in job.get("components", []) if isinstance(c, dict)]
        if not components:
            return "flowchart TD\n    empty[\"No components detected\"]"

        component_by_name = {
            c.get("unique_name"): c
            for c in components
            if c.get("unique_name")
        }
        node_ids = {}
        lines = ["flowchart TD"]

        def node_id(name):
            key = name or "component"
            if key not in node_ids:
                node_ids[key] = f"n{len(node_ids) + 1}"
            return node_ids[key]

        def label(component, fallback):
            ctype = component.get("component_type", "Component") if component else "Component"
            unique_name = component.get("unique_name", fallback) if component else fallback
            text = unique_name if unique_name and unique_name != ctype else ctype
            if unique_name and unique_name != ctype:
                text = f"{unique_name}\n{ctype}"
            return self._mermaid_label(text)

        def is_decision(component):
            if not component:
                return False
            ctype = component.get("component_type", "")
            return any(token in ctype for token in ("Filter", "Switch", "Assert", "Validation"))

        for component in components:
            name = component.get("unique_name") or component.get("component_type", "Component")
            shape_label = label(component, name)
            if is_decision(component):
                lines.append(f"    {node_id(name)}{{\"{shape_label}\"}}")
            else:
                lines.append(f"    {node_id(name)}[\"{shape_label}\"]")

        connections = [
            c for c in job.get("connections", [])
            if isinstance(c, dict) and c.get("source") and c.get("target")
        ]
        if connections:
            for conn in connections[:80]:
                source = conn.get("source")
                target = conn.get("target")
                connector = self._connector_label(conn.get("connector", ""))
                if connector:
                    lines.append(f"    {node_id(source)} -->|{connector}| {node_id(target)}")
                else:
                    lines.append(f"    {node_id(source)} --> {node_id(target)}")
            return "\n".join(lines)

        names = [
            c.get("unique_name") or c.get("component_type", f"Component {idx + 1}")
            for idx, c in enumerate(components[:80])
        ]
        for source, target in zip(names, names[1:]):
            lines.append(f"    {node_id(source)} --> {node_id(target)}")
        return "\n".join(lines)

    def _connector_label(self, connector):
        connector = str(connector or "").strip()
        if not connector:
            return ""
        friendly = {
            "FLOW": "Main",
            "ITERATE": "Iterate",
            "SUBJOB_OK": "OnSubjobOK",
            "SUBJOB_ERROR": "OnSubjobError",
            "COMPONENT_OK": "OnComponentOK",
            "COMPONENT_ERROR": "OnComponentError",
            "RUN_IF": "RunIf",
        }.get(connector, connector)
        return self._mermaid_label(friendly).replace("|", "/")

    def _mermaid_label(self, value):
        return (
            str(value or "")
            .replace("\\", "\\\\")
            .replace('"', "'")
            .replace("\r", " ")
            .replace("\n", "\\n")
        )
