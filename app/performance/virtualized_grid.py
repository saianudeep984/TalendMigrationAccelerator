from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.performance.pagination import PageResult, ServerSidePaginator


@dataclass(frozen=True)
class VirtualGridWindow:
    rows: list[Any]
    start: int
    end: int
    total_rows: int
    row_height: int
    viewport_height: int


class VirtualizedGrid:
    """Returns only rows visible in the current viewport/window."""

    def __init__(self, row_height: int = 32, overscan: int = 5) -> None:
        self.row_height = max(1, int(row_height))
        self.overscan = max(0, int(overscan))
        self.paginator = ServerSidePaginator()

    def window(self, rows: Iterable[Any], scroll_offset: int = 0, viewport_height: int = 640) -> VirtualGridWindow:
        data = list(rows or [])
        visible = max(1, int(viewport_height) // self.row_height)
        start = max(0, int(scroll_offset) // self.row_height - self.overscan)
        end = min(len(data), start + visible + self.overscan * 2)
        return VirtualGridWindow(data[start:end], start, end, len(data), self.row_height, int(viewport_height))

    def query_window(
        self,
        rows: Iterable[Any],
        scroll_offset: int = 0,
        viewport_height: int = 640,
        search: str = "",
        filters: Mapping[str, Any] | None = None,
        sort_by: str | None = None,
        sort_desc: bool = False,
    ) -> VirtualGridWindow:
        page: PageResult = self.paginator.query(rows, page=0, page_size=10**9, search=search, filters=filters, sort_by=sort_by, sort_desc=sort_desc)
        return self.window(page.rows, scroll_offset, viewport_height)
