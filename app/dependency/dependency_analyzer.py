from defusedxml import ElementTree as ET
from typing import Dict, List
import os


class DependencyAnalyzer:

    def __init__(self, item_file: str):
        self.item_file = item_file

        self.dependencies = {
            "child_jobs": [],
            "contexts": [],
            "routines": [],
            "metadata_connections": [],
            "components": []
        }

    def analyze(self) -> Dict[str, List[str]]:
        """
        Main entry point for dependency analysis
        """

        if not os.path.exists(self.item_file):
            raise FileNotFoundError(
                f"File not found: {self.item_file}"
            )

        try:
            tree = ET.parse(self.item_file)
            root = tree.getroot()

            self.extract_components(root)
            self.extract_trunjob_dependencies(root)
            self.extract_contexts(root)
            self.extract_routines(root)
            self.extract_metadata_connections(root)

            # Remove duplicates
            for key in self.dependencies:
                self.dependencies[key] = list(
                    set(self.dependencies[key])
                )

            graph_info = self._build_graph_info()
            self.dependencies.update(graph_info)
            return self.dependencies

        except ET.ParseError as e:
            raise ValueError(
                f"Invalid XML file: {self.item_file}"
            ) from e

    def extract_components(self, root) -> None:
        """
        Extract all Talend components
        """

        for node in root.iter():
            component_name = node.attrib.get("componentName")

            if component_name:
                self.dependencies["components"].append(
                    component_name
                )

    def extract_trunjob_dependencies(self, root) -> None:
        """
        Extract child job dependencies from tRunJob components.

        The child job name lives inside an <elementParameter> child element
        with name="PROCESS" (or "JOB_NAME" / "CHILD_JOB" in some Talend
        versions) — NOT in the label/uniqueName attribute of the node itself.
        """

        for node in root.iter():
            component_name = node.attrib.get("componentName")

            if component_name != "tRunJob":
                continue

            # Walk the elementParameter children to find the child job ref
            child_job = None
            for param in node.iter():
                clean_tag = param.tag
                if "}" in clean_tag:
                    clean_tag = clean_tag.split("}", 1)[1]
                if clean_tag != "elementParameter":
                    continue

                param_name = param.attrib.get("name", "")
                if param_name in ("PROCESS", "JOB_NAME", "CHILD_JOB",
                                  "PROCESS_NAME", "SUBPROCESS"):
                    raw_value = param.attrib.get("value", "").strip()
                    if raw_value:
                        # Strip surrounding quotes that Talend sometimes adds
                        child_job = raw_value.strip('"').strip("'")
                        break

            # Normalise: remove .item suffix and trailing _major.minor version
            if child_job:
                import re
                child_job = child_job.replace(".item", "")
                child_job = re.sub(r'_\d+\.\d+$', '', child_job)

            if child_job:
                self.dependencies["child_jobs"].append(child_job)

    def extract_contexts(self, root) -> None:
        """
        Extract context variables/groups
        """

        for node in root.iter():

            # Check multiple attributes
            for attr_value in node.attrib.values():

                if (
                    isinstance(attr_value, str)
                    and "context" in attr_value.lower()
                ):
                    self.dependencies["contexts"].append(
                        attr_value
                    )

    def extract_routines(self, root) -> None:
        """
        Extract routine usage
        """

        common_routines = [
            "StringHandling",
            "TalendDate",
            "Numeric",
            "DataOperation",
            "SQLike",
            "Relational"
        ]

        for node in root.iter():

            for attr_value in node.attrib.values():

                if isinstance(attr_value, str):

                    for routine in common_routines:

                        if routine in attr_value:
                            self.dependencies["routines"].append(
                                attr_value
                            )

    def extract_metadata_connections(self, root) -> None:
        """
        Extract metadata connectors
        """

        for node in root.iter():

            connector = (
                node.attrib.get("connectorName")
                or node.attrib.get("connection")
            )

            if connector:
                self.dependencies[
                    "metadata_connections"
                ].append(connector)

    def _build_graph_info(self):
        job_name = os.path.basename(self.item_file).replace(".item", "")
        import re
        job_name = re.sub(r'_\d+\.\d+$', '', job_name)
        relationships = [(job_name, child) for child in self.dependencies.get("child_jobs", [])]
        from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder

        builder = DependencyGraphBuilder()
        graph = builder.build_from_relationships(relationships)
        return {
            "relationships": relationships,
            "parent_jobs": [job_name] if relationships else [],
            "graph_object": graph,
            "dependency_statistics": {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "parent_jobs": 1 if relationships else 0,
                "child_jobs": len(self.dependencies.get("child_jobs", [])),
            },
        }
