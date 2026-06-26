from app.performance.cache_manager import AnalysisCacheManager
from app.performance.cache_metrics import CacheMetricsEngine
from app.performance.incremental_analysis import IncrementalAnalysisFramework
from app.performance.materialized_cache import MaterializedAnalysisCache


def _jobs():
    return [
        {
            "job_data": {
                "job_name": "JobA",
                "components": [
                    {"unique_name": "input_1", "component_type": "tFileInputDelimited"},
                    {"unique_name": "map_1", "component_type": "tMap"},
                ],
            },
            "dependencies": {"children": ["JobB"]},
            "complexity": {"level": "LOW"},
            "cloud_readiness": {"rag": "GREEN"},
        },
        {"job_data": {"job_name": "JobB", "components": []}},
    ]


def test_on_demand_job360_analyzes_only_selected_job(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    inc = IncrementalAnalysisFramework(cache)
    calls = []

    result = inc.analyze_job360(_jobs(), "JobA", lambda job: calls.append(job["job_data"]["job_name"]) or {"job": job["job_data"]["job_name"]})
    repeat = inc.analyze_job360(_jobs(), "JobA", lambda job: {"job": "wrong"})

    assert result == {"job": "JobA"}
    assert repeat == {"job": "JobA"}
    assert calls == ["JobA"]
    assert inc.analyze_job360(_jobs(), "Missing") is None


def test_on_demand_lineage_path_analyzes_only_selected_node(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    inc = IncrementalAnalysisFramework(cache)
    lineage = {"edges": [{"source": "A", "target": "B"}, {"source": "C", "target": "D"}]}

    result = inc.analyze_lineage_path(lineage, "A")

    assert result["edge_count"] == 1
    assert result["edges"] == [{"source": "A", "target": "B"}]


def test_incremental_component_and_asset_analysis_are_cached(tmp_path):
    cache = AnalysisCacheManager(MaterializedAnalysisCache(tmp_path), CacheMetricsEngine(), {})
    inc = IncrementalAnalysisFramework(cache)
    calls = {"component": 0, "asset": 0}

    component = inc.analyze_component(_jobs()[0], "map_1", lambda c: calls.__setitem__("component", calls["component"] + 1) or c["component_type"])
    component_again = inc.analyze_component(_jobs()[0], "map_1", lambda c: "wrong")
    asset = inc.analyze_asset([{"asset_id": "table.customer", "type": "table"}], "table.customer", lambda a: calls.__setitem__("asset", calls["asset"] + 1) or a["type"])
    asset_again = inc.analyze_asset([{"asset_id": "table.customer", "type": "table"}], "table.customer", lambda a: "wrong")

    assert component == "tMap"
    assert component_again == "tMap"
    assert asset == "table"
    assert asset_again == "table"
    assert calls == {"component": 1, "asset": 1}
