from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class PageResult:
    rows: list[Any]
    page: int
    page_size: int
    total_rows: int
    total_pages: int


class ServerSidePaginator:
    """Search/sort/filter/page large in-memory datasets without rendering all rows."""

    def __init__(self, page_size: int = 100) -> None:
        self.page_size = max(1, int(page_size))

    def query(
        self,
        rows: Iterable[Any],
        page: int = 0,
        page_size: int | None = None,
        search: str = "",
        filters: Mapping[str, Any] | None = None,
        sort_by: str | None = None,
        sort_desc: bool = False,
    ) -> PageResult:
        size = max(1, int(page_size or self.page_size))
        data = list(rows or [])
        if search:
            needle = search.lower()
            data = [row for row in data if needle in self._search_blob(row)]
        for key, expected in (filters or {}).items():
            if expected in (None, "", []):
                continue
            values = set(expected) if isinstance(expected, (list, tuple, set)) else {expected}
            data = [row for row in data if self._value(row, key) in values]
        if sort_by:
            data.sort(key=lambda row: self._sort_value(row, sort_by), reverse=sort_desc)
        total = len(data)
        total_pages = (total + size - 1) // size if total else 0
        page = max(0, min(int(page), max(0, total_pages - 1)))
        start = page * size
        return PageResult(data[start:start + size], page, size, total, total_pages)

    def job_inventory(self, jobs: Iterable[Mapping[str, Any]], **kwargs: Any) -> PageResult:
        rows = []
        for job in jobs or []:
            data = job.get("job_data", {})
            rows.append({
                "job_name": data.get("job_name"),
                "components": len(data.get("components", [])),
                "complexity": job.get("complexity", {}).get("level") or job.get("complexity", {}).get("complexity"),
                "readiness": job.get("cloud_readiness", {}).get("rag"),
                "raw": job,
            })
        return self.query(rows, **kwargs)

    def portfolio(self, projects: Iterable[Mapping[str, Any]], **kwargs: Any) -> PageResult:
        rows = []
        for project in projects or []:
            rows.append({
                "project_name": project.get("project_name") or project.get("name"),
                "job_count": project.get("job_count", len(project.get("jobs", []))),
                "readiness": project.get("readiness"),
                "risk_score": project.get("risk_score"),
                "raw": project,
            })
        return self.query(rows, **kwargs)

    def _search_blob(self, row: Any) -> str:
        if isinstance(row, Mapping):
            return " ".join(str(v).lower() for k, v in row.items() if k != "raw")
        return str(row).lower()

    def _value(self, row: Any, key: str) -> Any:
        if isinstance(row, Mapping):
            current: Any = row
            for part in key.split("."):
                if not isinstance(current, Mapping):
                    return None
                current = current.get(part)
            return current
        return getattr(row, key, None)

    def _sort_value(self, row: Any, key: str) -> tuple[int, Any]:
        value = self._value(row, key)
        return (value is None, value)
