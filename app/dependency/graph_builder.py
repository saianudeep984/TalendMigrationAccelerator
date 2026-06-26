
class DependencyGraphBuilder:
    def __init__(self):
        from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder as TiapBuilder
        self._builder = TiapBuilder()
        self.graph = self._builder.graph

    def build_graph(self, job_name, dependencies):
        self.graph.add_node(job_name)
        for child in dependencies.get("child_jobs",[]):
            if child:
                self.graph.add_edge(job_name,child)
        return self.graph

    def build_from_relationships(self, relationships):
        self.graph = self._builder.build_from_relationships(relationships)
        return self.graph

    def build_dependency_graph(self, all_jobs):
        self.graph = self._builder.build(all_jobs)
        return self.graph

    def build_lineage_graph(self, all_jobs):
        return self.build_dependency_graph(all_jobs)

    def build_impact_graph(self, all_jobs, job_name=None):
        graph = self.build_dependency_graph(all_jobs)
        if job_name and job_name in graph:
            import networkx as nx
            nodes = {job_name, *nx.ancestors(graph, job_name), *nx.descendants(graph, job_name)}
            self.graph = graph.subgraph(nodes).copy()
        return self.graph

    def export_graph_data(self):
        return {"nodes":list(self.graph.nodes()),
                "edges":[{"source":s,"target":t} for s,t in self.graph.edges()]}
