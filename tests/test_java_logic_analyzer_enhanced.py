from app.analyzers.java_logic_analyzer import analyze_java_logic


def test_java_logic_analyzer_builds_inventory_risk_explanation_and_recommendations():
    job = {
        "job_data": {
            "job_name": "JavaJob",
            "components": [
                {
                    "component_type": "tJavaRow",
                    "unique_name": "tJavaRow_1",
                    "parameters": {
                        "CODE": (
                            "import org.apache.commons.lang3.StringUtils;\n"
                            "try {\n"
                            "  String value = MyRoutine.clean(input_row.name);\n"
                            "  output_row.name = StringUtils.trim(value);\n"
                            "  java.sql.Connection c = DriverManager.getConnection(url);\n"
                            "} catch (Exception e) { throw e; }"
                        )
                    },
                },
                {
                    "component_type": "tJavaFlex",
                    "unique_name": "tJavaFlex_1",
                    "parameters": {
                        "CODE": "Runtime.getRuntime().exec(\"legacy.sh\");"
                    },
                },
            ],
        }
    }

    result = analyze_java_logic(job)

    assert result["java_component_count"] == 2
    assert {row["Type"] for row in result["java_inventory"]} == {"tJavaRow", "tJavaFlex"}
    assert "MyRoutine" in result["routine_usage"]
    assert "org.apache.commons" in result["external_jars"]
    assert result["overall_risk"] == "CRITICAL"
    assert "overall CRITICAL migration risk" in result["ai_explanation"]
    assert any(rec["category"] == "External Libraries" for rec in result["recommendations"])
    assert any(rec["priority"] == "CRITICAL" for rec in result["recommendations"])

