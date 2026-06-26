
def analyze_dependencies(all_jobs):
    from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder

    analysis = DependencyGraphBuilder().analyze(all_jobs)
    return {
        "relationships": analysis["relationships"],
        "parent_jobs": analysis["parent_jobs"],
        "child_jobs": analysis["child_jobs"],
        "graph_object": analysis["graph_object"],
        "graph": analysis["graph_object"],
        "dependency_statistics": analysis["dependency_statistics"],
        "relationship_count": len(analysis["relationships"]),
        "dependency_chains": analysis["dependency_chains"],
        "critical_paths": analysis["critical_paths"],
        "circular_dependencies": analysis["circular_dependencies"],
    }
