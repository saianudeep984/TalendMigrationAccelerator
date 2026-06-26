from app.analyzers.readiness_scorer import calculate_readiness_score


def _job(name, readiness="HIGH", child_jobs=0, components=None):
    return {
        "job_data": {
            "job_name": name,
            "components": components or [{"component_type": "tLogRow"}],
        },
        "cloud_readiness": {"readiness": readiness},
        "estimation": {"child_job_count": child_jobs},
    }


def test_calculate_readiness_score_returns_green_amber_red_strings():
    green = calculate_readiness_score(
        [_job("green")],
        {"impacted_jobs": 0},
        [],
    )
    amber = calculate_readiness_score(
        [_job("amber", readiness="MEDIUM", child_jobs=8)],
        {"impacted_jobs": 0},
        [{"count": 1, "impacted_jobs": ["amber"]}],
    )
    red = calculate_readiness_score(
        [_job("red", readiness="LOW", child_jobs=30)],
        {"impacted_jobs": 1},
        [{"count": 1, "impacted_jobs": ["red"]}],
    )

    assert green["overall"] == "GREEN"
    assert amber["overall"] == "AMBER"
    assert red["overall"] == "RED"
    assert all(result["overall"] in {"GREEN", "AMBER", "RED"} for result in (green, amber, red))
