from __future__ import annotations

from itertools import islice
from typing import Any, Iterable, Iterator, List, Mapping


class PerformanceAwareDataLoader:
    """Incremental loader for large job/component/lineage/dependency collections."""

    def __init__(self, page_size: int = 250) -> None:
        self.page_size = max(1, int(page_size))

    def batches(self, items: Iterable[Any], page_size: int | None = None) -> Iterator[List[Any]]:
        size = max(1, int(page_size or self.page_size))
        iterator = iter(items or [])
        while True:
            batch = list(islice(iterator, size))
            if not batch:
                break
            yield batch

    def page(self, items: Iterable[Any], page: int = 0, page_size: int | None = None) -> List[Any]:
        size = max(1, int(page_size or self.page_size))
        start = max(0, int(page)) * size
        return list(islice(iter(items or []), start, start + size))

    def first_page(self, items: Iterable[Any], page_size: int | None = None) -> List[Any]:
        return next(self.batches(items, page_size), [])

    def jobs(self, jobs: Iterable[Mapping[str, Any]], page: int = 0) -> List[Mapping[str, Any]]:
        return self.page(jobs, page)

    def components(self, jobs: Iterable[Mapping[str, Any]], page: int = 0) -> List[Any]:
        def stream() -> Iterator[Any]:
            for job in jobs or []:
                yield from job.get("job_data", {}).get("components", [])
        return self.page(stream(), page)

    def lineage_edges(self, lineage: Mapping[str, Any], page: int = 0) -> List[Any]:
        return self.page((lineage or {}).get("edges", []), page)

    def dependencies(self, jobs: Iterable[Mapping[str, Any]], page: int = 0) -> List[Any]:
        rows = ({"job": j.get("job_data", {}).get("job_name"), "dependencies": j.get("dependencies", {})} for j in jobs or [])
        return self.page(rows, page)
