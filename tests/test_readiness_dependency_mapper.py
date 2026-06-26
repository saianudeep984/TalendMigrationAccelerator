from app.readiness.dependency_mapper import (
    READINESS_MODULES,
    build_dependency_map,
    find_orphan_modules,
)


def test_map_covers_all_readiness_modules():
    m = build_dependency_map(".")
    assert set(m.keys()) == set(READINESS_MODULES)


def test_component_compatibility_has_one_dependent():
    m = build_dependency_map(".")
    deps = m["app.readiness.component_compatibility"]["imported_by"]
    assert "app.analyzers.readiness_scorer" in deps


def test_readiness_scorer_widely_imported():
    m = build_dependency_map(".")
    deps = m["app.analyzers.readiness_scorer"]["imported_by"]
    assert "app.ui.streamlit_app" in deps
    assert len(deps) >= 10


def test_orphan_modules_removed_after_f4_2():
    """F4.2 deleted the zero-import dead modules
    (migration_assistant.migration_readiness, readiness.cloud_blockers,
    readiness.talend8_readiness, tiap.assessment.migration_readiness).
    tiap.assessment.cloud_readiness remains a tested backward-compat
    alias (see test_cloud_readiness_canonical_engine.py) and is exempt."""
    m = build_dependency_map(".")
    orphans = set(find_orphan_modules(m))
    assert orphans <= {"app.tiap.assessment.cloud_readiness"}
    assert "app.readiness.cloud_blockers" not in m
    assert "app.readiness.talend8_readiness" not in m
    assert "app.migration_assistant.migration_readiness" not in m
    assert "app.tiap.assessment.migration_readiness" not in m
