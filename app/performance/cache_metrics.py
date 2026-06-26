from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CacheMetric:
    hits: int = 0
    misses: int = 0
    writes: int = 0
    invalidations: int = 0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    bytes_estimate: int = 0

    @property
    def total_reads(self) -> int:
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        return self.hits / self.total_reads if self.total_reads else 0.0

    @property
    def miss_ratio(self) -> float:
        return self.misses / self.total_reads if self.total_reads else 0.0

    @property
    def lifetime_seconds(self) -> float:
        return max(0.0, time.time() - self.created_at)


class CacheMetricsEngine:
    """Tracks cache efficiency without depending on Streamlit."""

    def __init__(self) -> None:
        self._metrics: Dict[str, CacheMetric] = {}

    def _metric(self, namespace: str) -> CacheMetric:
        return self._metrics.setdefault(namespace, CacheMetric())

    def record_hit(self, namespace: str) -> None:
        metric = self._metric(namespace)
        metric.hits += 1
        metric.last_accessed = time.time()

    def record_miss(self, namespace: str) -> None:
        metric = self._metric(namespace)
        metric.misses += 1
        metric.last_accessed = time.time()

    def record_write(self, namespace: str, value: Any = None) -> None:
        metric = self._metric(namespace)
        metric.writes += 1
        metric.last_accessed = time.time()
        try:
            metric.bytes_estimate = sys.getsizeof(value)
        except Exception:
            metric.bytes_estimate = 0

    def record_invalidation(self, namespace: str) -> None:
        metric = self._metric(namespace)
        metric.invalidations += 1
        metric.last_accessed = time.time()

    def snapshot(self) -> Dict[str, Any]:
        total_hits = sum(m.hits for m in self._metrics.values())
        total_misses = sum(m.misses for m in self._metrics.values())
        total_reads = total_hits + total_misses
        return {
            "cache_hits": total_hits,
            "cache_misses": total_misses,
            "cache_efficiency": total_hits / total_reads if total_reads else 0.0,
            "cache_size_bytes": sum(m.bytes_estimate for m in self._metrics.values()),
            "namespaces": {
                key: {
                    "hits": metric.hits,
                    "misses": metric.misses,
                    "writes": metric.writes,
                    "invalidations": metric.invalidations,
                    "hit_ratio": metric.hit_ratio,
                    "miss_ratio": metric.miss_ratio,
                    "cache_lifetime_seconds": metric.lifetime_seconds,
                    "bytes_estimate": metric.bytes_estimate,
                }
                for key, metric in self._metrics.items()
            },
        }


_METRICS = CacheMetricsEngine()


def get_cache_metrics() -> CacheMetricsEngine:
    return _METRICS
