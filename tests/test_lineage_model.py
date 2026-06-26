from app.lineage import (
    EdgeType,
    LineageEdge,
    LineageGraph,
    LineageNode,
    LineagePath,
    NodeType,
)


def _build_sample_graph():
    """Two-hop graph: source table -> tMap component -> target table."""
    src = LineageNode(
        id="job1:source_table:mysql.companies",
        node_type=NodeType.SOURCE_TABLE,
        label="companies",
        system_type="MySQL",
        job_name="job1",
        physical_identity="mysql:companies",
    )
    tmap = LineageNode(
        id="job1:component:tMap_1",
        node_type=NodeType.COMPONENT,
        label="tMap_1",
        job_name="job1",
    )
    tgt = LineageNode(
        id="job1:target_table:mysql.dim_company",
        node_type=NodeType.TARGET_TABLE,
        label="dim_company",
        system_type="MySQL",
        job_name="job1",
        physical_identity="mysql:dim_company",
    )

    graph = LineageGraph(nodes=[src, tmap, tgt])

    e1 = LineageEdge(
        source_node_id=src.id,
        target_node_id=tmap.id,
        edge_type=EdgeType.DATA_FLOW,
        job_name="job1",
        rule="Direct Copy",
        rule_type="direct",
        expression="row1.companyid",
        source_column="companyid",
        target_column="companyid",
    )
    e2 = LineageEdge(
        source_node_id=tmap.id,
        target_node_id=tgt.id,
        edge_type=EdgeType.DATA_FLOW,
        job_name="job1",
        rule="Function Transform",
        rule_type="expression",
        expression="TalendDate.getCurrentDate()",
        source_column="companyid",
        target_column="created_at",
    )
    graph.add_edge(e1)
    graph.add_edge(e2)
    return graph, src, tmap, tgt, e1, e2


def test_graph_build_and_counts():
    graph, *_ = _build_sample_graph()
    assert graph.node_count == 3
    assert graph.edge_count == 2


def test_duplicate_edge_is_deduplicated():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()
    same_edge = LineageEdge(
        source_node_id=src.id,
        target_node_id=tmap.id,
        edge_type=EdgeType.DATA_FLOW,
        job_name="job1",
        rule="Direct Copy",
        rule_type="direct",
        expression="row1.companyid",
        source_column="companyid",
        target_column="companyid",
    )
    graph.add_edge(same_edge)
    assert graph.edge_count == 2  # unchanged


def test_add_edge_requires_known_nodes():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()
    bad_edge = LineageEdge(
        source_node_id="does-not-exist",
        target_node_id=tgt.id,
        edge_type=EdgeType.DATA_FLOW,
    )
    try:
        graph.add_edge(bad_edge)
        assert False, "expected ValueError for unknown source_node_id"
    except ValueError:
        pass


def test_neighbors_one_hop():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()
    assert [n.id for n in graph.neighbors(src.id, "out")] == [tmap.id]
    assert [n.id for n in graph.neighbors(tgt.id, "in")] == [tmap.id]
    assert [n.id for n in graph.neighbors(tmap.id, "both")] == [tgt.id, src.id]


def test_find_nodes_by_physical_identity():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()
    found = graph.find_nodes_by_physical_identity("mysql:companies")
    assert len(found) == 1
    assert found[0].id == src.id
    assert graph.find_nodes_by_physical_identity("") == []


def test_graph_json_round_trip():
    graph, *_ = _build_sample_graph()
    restored = LineageGraph.from_json(graph.to_json())
    assert restored.node_count == graph.node_count
    assert restored.edge_count == graph.edge_count
    assert restored.get_node("job1:source_table:mysql.companies").label == "companies"


def test_to_mermaid_contains_nodes_and_edges():
    graph, *_ = _build_sample_graph()
    mermaid = graph.to_mermaid()
    assert mermaid.startswith("graph LR")
    assert "companies" in mermaid
    assert "dim_company" in mermaid
    assert "Direct Copy" in mermaid


def test_merge_two_jobs_exposes_bridge_candidates():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()

    src2 = LineageNode(
        id="job2:source_table:mysql.dim_company",
        node_type=NodeType.SOURCE_TABLE,
        label="dim_company",
        system_type="MySQL",
        job_name="job2",
        physical_identity="mysql:dim_company",
    )
    tgt2 = LineageNode(
        id="job2:target_table:snowflake.fact_company",
        node_type=NodeType.TARGET_TABLE,
        label="fact_company",
        system_type="Snowflake",
        job_name="job2",
        physical_identity="snowflake:fact_company",
    )
    job2_graph = LineageGraph(nodes=[src2, tgt2])
    job2_graph.add_edge(
        LineageEdge(
            source_node_id=src2.id,
            target_node_id=tgt2.id,
            edge_type=EdgeType.DATA_FLOW,
            job_name="job2",
            rule="Direct Copy",
            rule_type="direct",
        )
    )

    merged = graph.merge(job2_graph)
    assert merged.node_count == 5
    assert merged.edge_count == 3

    # job1's target table and job2's source table are the same physical
    # object (different ids, same physical_identity) -- this is the
    # primitive a future repository-level builder uses to bridge jobs.
    bridge_candidates = merged.find_nodes_by_physical_identity("mysql:dim_company")
    assert {n.id for n in bridge_candidates} == {tgt.id, src2.id}


def test_lineage_path_from_edges_and_describe():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()
    path = LineagePath.from_edges(graph, [e1, e2])

    assert path.hop_count == 2
    assert path.start_node.id == src.id
    assert path.end_node.id == tgt.id
    assert path.expressions == ["row1.companyid", "TalendDate.getCurrentDate()"]
    assert "Direct Copy" in path.describe()
    assert "Function Transform" in path.describe()


def test_lineage_path_seed_and_extend():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()

    seed = LineagePath.single_node(src)
    assert seed.hop_count == 0
    assert seed.start_node.id == seed.end_node.id == src.id

    extended = seed.extend(e1, tmap)
    assert extended.hop_count == 1
    assert extended.end_node.id == tmap.id


def test_lineage_path_rejects_malformed_chain():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()
    try:
        LineagePath(nodes=[src, tgt], edges=[e1])  # e1 ends at tmap, not tgt
        assert False, "expected ValueError for a non-contiguous path"
    except ValueError:
        pass


def test_lineage_path_json_round_trip():
    graph, src, tmap, tgt, e1, e2 = _build_sample_graph()
    path = LineagePath.from_edges(graph, [e1, e2])
    restored = LineagePath.from_dict(path.to_dict())
    assert restored.hop_count == path.hop_count
    assert restored.describe() == path.describe()
