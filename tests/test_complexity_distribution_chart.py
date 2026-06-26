from app.ui.design_system_v2 import (
    complexity_breakdown_from_jobs,
    render_complexity_distribution_chart,
)


def test_complexity_breakdown_from_jobs_counts_known_labels():
    jobs = [
        {"estimation": {"complexity": "LOW"}},
        {"estimation": {"complexity": "LOW"}},
        {"estimation": {"complexity": "MEDIUM"}},
        {"estimation": {"complexity": "HIGH"}},
        {"estimation": {"complexity": "CRITICAL"}},
        {"estimation": {}},
        {},
    ]
    result = complexity_breakdown_from_jobs(jobs)
    assert result == {"LOW": 2, "MEDIUM": 1, "HIGH": 1, "CRITICAL": 1}


def test_complexity_breakdown_from_jobs_empty_list():
    assert complexity_breakdown_from_jobs([]) == {
        "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0
    }


def test_render_complexity_distribution_chart_pie_from_dict():
    from streamlit.testing.v1 import AppTest

    def _app():
        from app.ui.design_system_v2 import render_complexity_distribution_chart
        render_complexity_distribution_chart(by_complexity={"LOW": 3, "MEDIUM": 2}, key="t1")

    at = AppTest.from_function(_app)
    at.run(timeout=30)
    assert not at.exception


def test_render_complexity_distribution_chart_bar_mode():
    from streamlit.testing.v1 import AppTest

    def _app():
        from app.ui.design_system_v2 import render_complexity_distribution_chart
        render_complexity_distribution_chart(by_complexity={"HIGH": 1, "CRITICAL": 1}, chart_type="bar", key="t2")

    at = AppTest.from_function(_app)
    at.run(timeout=30)
    assert not at.exception


def test_render_complexity_distribution_chart_from_jobs():
    from streamlit.testing.v1 import AppTest

    def _app():
        from app.ui.design_system_v2 import render_complexity_distribution_chart
        jobs = [{"estimation": {"complexity": "LOW"}}, {"estimation": {"complexity": "HIGH"}}]
        render_complexity_distribution_chart(all_jobs=jobs, key="t3")

    at = AppTest.from_function(_app)
    at.run(timeout=30)
    assert not at.exception


def test_render_complexity_distribution_chart_empty_shows_caption():
    from streamlit.testing.v1 import AppTest

    def _app():
        from app.ui.design_system_v2 import render_complexity_distribution_chart
        render_complexity_distribution_chart(by_complexity={}, all_jobs=[], key="t4")

    at = AppTest.from_function(_app)
    at.run(timeout=30)
    assert not at.exception
    captions = [c.value for c in at.caption]
    assert any("run analysis first" in c for c in captions)
