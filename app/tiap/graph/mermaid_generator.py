from typing import Any, Dict, Sequence

from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder
from app.tiap.profiling.context_profiler import ContextProfiler
from app.tiap.profiling.joblet_profiler import JobletProfiler


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "Unknown"))


class MermaidGenerator:
    def repository_dependency_diagram(self, all_jobs: Sequence[Dict[str, Any]]) -> str:
        graph = DependencyGraphBuilder().build(all_jobs)
        return self.from_graph(graph)

    def job_dependency_diagram(self, all_jobs: Sequence[Dict[str, Any]], job_name: str = None) -> str:
        graph = DependencyGraphBuilder().build(all_jobs)
        if job_name and job_name in graph:
            nodes = {job_name, *graph.successors(job_name), *graph.predecessors(job_name)}
            graph = graph.subgraph(nodes).copy()
        return self.from_graph(graph)

    def joblet_dependency_diagram(self, all_jobs: Sequence[Dict[str, Any]]) -> str:
        matrix = JobletProfiler().profile(all_jobs)["joblet_dependency_matrix"]
        lines = ["graph TD"]
        for job, joblets in matrix.items():
            for joblet in joblets:
                lines.append(f"    {_safe_id(job)}[{job}] --> {_safe_id(joblet)}[{joblet}]")
        return "\n".join(lines) if len(lines) > 1 else "graph TD\n    EMPTY[No joblet dependencies]"

    def context_dependency_diagram(self, all_jobs: Sequence[Dict[str, Any]]) -> str:
        matrix = ContextProfiler().profile(all_jobs)["repository_context_matrix"]
        lines = ["graph TD"]
        for job, contexts in matrix.items():
            for context in contexts:
                lines.append(f"    {_safe_id(job)}[{job}] --> {_safe_id(context)}[{context}]")
        return "\n".join(lines) if len(lines) > 1 else "graph TD\n    EMPTY[No context dependencies]"

    def from_graph(self, graph) -> str:
        lines = ["graph TD"]
        for source, target in graph.edges():
            lines.append(f"    {_safe_id(source)}[{source}] --> {_safe_id(target)}[{target}]")
        if len(lines) == 1:
            for node in graph.nodes():
                lines.append(f"    {_safe_id(node)}[{node}]")
        return "\n".join(lines) if len(lines) > 1 else "graph TD\n    EMPTY[No dependencies]"


def generate_mermaid(graph):
    return MermaidGenerator().from_graph(graph)
