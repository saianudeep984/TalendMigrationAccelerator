"""
Backward-compatible re-export. Canonical implementation now lives in
app.analyzers.cloud_readiness (F2.2/F2.3 unified readiness architecture).
"""
from app.analyzers.cloud_readiness import CloudReadinessAnalyzer  # noqa: F401
