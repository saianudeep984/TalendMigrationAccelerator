from app.migration_intelligence.critical_path_analyzer import CriticalPathAnalyzer
from app.migration_intelligence.dependency_graph import DependencyGraphEngine


def test_graph_detects_job_and_shared_dependencies(tmp_path):
    jobs = [{"job_data": {"job_name": "Parent", "components": []}, "dependencies": {"child_jobs": ["Child"], "contexts": ["Shared"]}},
            {"job_data": {"job_name": "Child", "components": []}, "dependencies": {"contexts": ["Shared"]}}]
    graph = DependencyGraphEngine().build(jobs)
    assert {"source": "Parent", "target": "Child", "type": "parent_child"} in graph["edges"]
    assert any(n["id"] == "context:Shared" for n in graph["nodes"])
    path = tmp_path / "graph.json"
    assert DependencyGraphEngine.save(graph, path) == str(path)


def test_critical_path_and_downstream_impact():
    graph = {"job_names": ["A", "B", "C"], "edges": [
        {"source": "A", "target": "B", "type": "parent_child"},
        {"source": "B", "target": "C", "type": "parent_child"}]}
    result = CriticalPathAnalyzer().analyze(graph)
    assert result["critical_paths"][0] == ["A", "B", "C"]
    assert result["jobs"][0]["job_name"] == "A"
