from app.migration_intelligence.wave_planner import MigrationWavePlanner


def test_children_are_scheduled_before_calling_parents():
    jobs = {"jobs": [{"job_name": n, "complexity": "LOW"} for n in ("Parent", "Child", "Leaf")]}
    graph = {"job_names": ["Parent", "Child", "Leaf"], "edges": [
        {"source": "Parent", "target": "Child", "type": "parent_child"},
        {"source": "Child", "target": "Leaf", "type": "parent_child"}]}
    result = MigrationWavePlanner().plan(jobs, graph)
    assert result["valid"]
    assert result["assignment"]["Leaf"] < result["assignment"]["Child"] < result["assignment"]["Parent"]


def test_cycles_are_kept_in_a_safe_atomic_wave():
    graph = {"job_names": ["A", "B"], "edges": [{"source": "A", "target": "B", "type": "parent_child"}, {"source": "B", "target": "A", "type": "parent_child"}]}
    result = MigrationWavePlanner().plan({"jobs": []}, graph)
    assert result["cycles"] == [["A", "B"]]
    assert result["assignment"]["A"] == result["assignment"]["B"]
