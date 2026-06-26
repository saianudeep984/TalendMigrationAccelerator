from app.ui.cached_lineage_page import (
    affected_columns,
    downstream_jobs,
    related_tables,
    upstream_jobs,
)


def _cache_shape():
    return {
        "job_lineage": {
            "extract.py": {"sql_operations": []},
            "load.py": {"sql_operations": []},
            "report.py": {"sql_operations": []},
        },
        "dependency_graph": {
            "extract.py": {"imports": ["common.py"], "imported_by": ["report.py"], "package": "app"},
            "load.py": {"imports": [], "imported_by": [], "package": "app"},
            "report.py": {"imports": ["extract.py"], "imported_by": [], "package": "app"},
            "common.py": {"imports": [], "imported_by": ["extract.py"], "package": "app"},
        },
        "table_lineage": {
            "customers": {
                "table_name": "customers",
                "reads": [
                    {
                        "module": "extract.py",
                        "statement": "SELECT id, name FROM customers",
                        "line": 10,
                    }
                ],
                "writes": [
                    {
                        "module": "load.py",
                        "statement": "INSERT INTO customers (id, name) VALUES (?, ?)",
                        "line": 20,
                    }
                ],
                "ddl": [],
                "modules": ["extract.py", "load.py"],
            },
            "audit": {
                "table_name": "audit",
                "reads": [],
                "writes": [
                    {
                        "module": "extract.py",
                        "statement": "UPDATE audit SET status = ? WHERE id = ?",
                        "line": 30,
                    }
                ],
                "ddl": [],
                "modules": ["extract.py"],
            },
        },
    }


def test_cached_lineage_combines_dependencies_and_table_flow():
    data = _cache_shape()

    assert upstream_jobs(data, "extract.py") == ["common.py", "load.py"]
    assert downstream_jobs(data, "extract.py") == ["report.py"]


def test_cached_lineage_reports_affected_tables_and_columns():
    data = _cache_shape()

    assert related_tables(data, "extract.py") == [
        {"Table": "audit", "Reads": 0, "Writes": 1, "DDL": 0, "Access": "write"},
        {"Table": "customers", "Reads": 1, "Writes": 0, "DDL": 0, "Access": "read"},
    ]
    assert affected_columns(data, "extract.py") == [
        "audit.status",
        "customers.id",
        "customers.name",
    ]

