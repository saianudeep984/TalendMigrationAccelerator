import ast


def _src():
    with open("app/ui/repository_search_page.py", encoding="utf-8") as f:
        return f.read()


def _module_value(name):
    tree = ast.parse(_src())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found")


def test_global_search_filters_match_required_scope():
    assert _module_value("_FILTER_OPTIONS") == [
        "All",
        "Jobs",
        "Components",
        "Source Tables",
        "Target Tables",
        "Source Columns",
        "Target Columns",
        "SQL",
        "Java",
        "Variables",
        "Mappings",
    ]


def test_global_search_uses_existing_metadata_only():
    src = _src()
    forbidden = (
        "find_talend_jobs",
        "safe_extract",
        "TalendJobParser",
        "os.walk",
        "glob(",
        "rglob(",
    )
    for token in forbidden:
        assert token not in src


def test_global_search_routes_to_job360_section():
    src = _src()
    assert 'st.session_state["_job360_open_job"] = job_name' in src
    assert 'st.session_state["_job360_open_category"] = category' in src
    assert '"SQL": "Technical Analysis"' in src
    assert '"Mapping": "Mapping & Lineage"' in src
    assert '"Source Table": "Architecture"' in src
