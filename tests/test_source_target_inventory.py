from app.parser.source_target_extractor import build_source_target_inventory


def test_source_inventory_prefers_tables_from_input_query():
    job_data = {
        "components": [
            {
                "component_type": "tMysqlInput",
                "unique_name": "tMysqlInput_1",
                "parameters": {
                    "TABLE": "configured_table",
                    "QUERY": (
                        "SELECT c.id, o.total "
                        "FROM sales.customers c "
                        "JOIN sales.orders o ON c.id = o.customer_id"
                    ),
                },
            }
        ]
    }

    inv = build_source_target_inventory(job_data)

    assert inv["source_names"] == ["sales.customers", "sales.orders"]
    assert [s["source"] for s in inv["sources"]] == ["query", "query"]

