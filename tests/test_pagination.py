import time

from app.performance.pagination import ServerSidePaginator
from app.performance.virtualized_grid import VirtualizedGrid


def test_server_side_pagination_search_sort_filter_handles_5000_jobs():
    jobs = [
        {
            "job_data": {"job_name": f"Job_{i:04d}", "components": [1] * (i % 7)},
            "complexity": {"level": "HIGH" if i % 10 == 0 else "LOW"},
            "cloud_readiness": {"rag": "GREEN" if i % 2 == 0 else "AMBER"},
        }
        for i in range(5000)
    ]
    pager = ServerSidePaginator(page_size=50)
    start = time.perf_counter()
    result = pager.job_inventory(jobs, page=0, search="Job_01", filters={"readiness": "GREEN"}, sort_by="job_name", sort_desc=True)
    elapsed = time.perf_counter() - start

    assert result.total_rows == 50
    assert len(result.rows) == 50
    assert result.rows[0]["job_name"] == "Job_0198"
    assert elapsed < 1.0


def test_portfolio_pagination_filters_and_sorts():
    projects = [{"name": f"P{i}", "job_count": i, "risk_score": 100 - i, "readiness": "RED" if i % 2 else "GREEN"} for i in range(100)]

    result = ServerSidePaginator(page_size=10).portfolio(projects, filters={"readiness": "RED"}, sort_by="risk_score")

    assert result.total_rows == 50
    assert result.rows[0]["risk_score"] == 1
    assert result.total_pages == 5


def test_virtualized_grid_renders_only_visible_rows():
    rows = [{"id": i, "name": f"Job_{i}"} for i in range(5000)]
    grid = VirtualizedGrid(row_height=20, overscan=2)
    start = time.perf_counter()
    window = grid.query_window(rows, scroll_offset=2000, viewport_height=200, search="Job")
    elapsed = time.perf_counter() - start

    assert window.total_rows == 5000
    assert window.start == 98
    assert len(window.rows) <= 14
    assert elapsed < 1.0
