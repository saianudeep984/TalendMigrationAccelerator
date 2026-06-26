"""
Defensive access helpers for TMA report generators.

These utilities make report code resilient to whether the caller passes a
dataclass instance (e.g. ExecutiveDashboard), a `to_dict()` result, or a
plain dict produced by legacy `_exec_business_model()`.

Two public helpers:

    safe_get(model, field, default=None)
        Field lookup that supports both attribute access and dict-style
        access, plus camelCase / snake_case name aliasing.

    sanitize_dataframe_for_streamlit(df)
        Coerces dict / list / set / mixed object columns to JSON strings
        so Streamlit's Arrow serialization layer never raises
        ArrowTypeError("Expected bytes, got dict") and similar errors
        when calling st.dataframe / st.table / st.data_editor.
"""
from __future__ import annotations

import json
from typing import Any


_CAMEL_OVERRIDES = {
    "total_jobs": "totalJobs",
    "analyzed_jobs": "analyzedJobs",
    "ready_jobs": "readyJobs",
    "total_components": "totalComponents",
    "cloud_readiness_status": "cloudReadinessStatus",
    "automation_pct": "automationPct",
    "manual_pct": "manualPct",
    "estimated_hours": "estimatedHours",
    "estimated_weeks": "estimatedWeeks",
    "estimated_days": "estimatedDays",
    "high_risk_count": "highRiskCount",
    "warning_jobs": "warningJobs",
    "failed_jobs": "failedJobs",
    "risk_label": "riskLabel",
    "complexity_breakdown": "complexityBreakdown",
    "total_routines": "totalRoutines",
    "total_joblets": "totalJoblets",
    "person_days": "personDays",
    "high_risk": "highRisk",
    "success_rate": "successRate",
}


def _to_camel(snake: str) -> str:
    if snake in _CAMEL_OVERRIDES:
        return _CAMEL_OVERRIDES[snake]
    parts = snake.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _to_snake(camel: str) -> str:
    out = []
    for i, c in enumerate(camel):
        if c.isupper() and i > 0:
            out.append("_")
        out.append(c.lower())
    return "".join(out)


def safe_get(model: Any, field: str, default: Any = None) -> Any:
    """
    Resolve `field` from `model` regardless of whether it is:

      * a dataclass / object  → uses getattr
      * a dict / Mapping      → uses key lookup (with camel/snake aliasing)
      * a `to_dict()`-able    → falls back to .to_dict() lookup

    Returns `default` if the field cannot be located.
    """
    if model is None:
        return default

    # 1. Direct attribute on dataclass / object.
    if hasattr(model, field):
        try:
            value = getattr(model, field)
            if value is not None:
                return value
        except Exception:
            pass

    # 2. Mapping / dict-style.
    if isinstance(model, dict):
        if field in model:
            return model[field]
        camel = _to_camel(field)
        if camel in model:
            return model[camel]
        snake = _to_snake(field)
        if snake in model:
            return model[snake]

    # 3. Fall back to .to_dict() if available.
    if hasattr(model, "to_dict") and callable(getattr(model, "to_dict")):
        try:
            data = model.to_dict()
        except Exception:
            data = None
        if isinstance(data, dict):
            if field in data:
                return data[field]
            camel = _to_camel(field)
            if camel in data:
                return data[camel]

    # 4. Try camelCase attribute on object.
    camel = _to_camel(field)
    if hasattr(model, camel):
        try:
            value = getattr(model, camel)
            if value is not None:
                return value
        except Exception:
            pass

    return default


def _coerce_cell(value: Any) -> Any:
    """Coerce a single cell value into something Arrow can serialize."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        try:
            if isinstance(value, (set, frozenset)):
                return json.dumps(sorted(list(value)), default=str)
            return json.dumps(value, default=str)
        except Exception:
            return str(value)
    # bytes, datetimes, custom objects → string
    try:
        return str(value)
    except Exception:
        return ""


def sanitize_dataframe_for_streamlit(df):
    """
    Make a pandas DataFrame safe for st.dataframe / st.table / st.data_editor.

    Pandas → Streamlit uses Arrow under the hood, which errors on mixed
    object columns and on non-primitive values like dict / list / set.
    This function returns a *copy* with such cells converted to JSON
    strings (or str(...) as a fallback) and forces every object dtype
    column to plain string dtype.

    Falls back to returning `df` unchanged when pandas isn't importable
    or when the input is not a DataFrame.
    """
    try:
        import pandas as pd  # local import to avoid hard dep at import time
    except Exception:
        return df

    if df is None:
        return df
    if not isinstance(df, pd.DataFrame):
        # Allow list-of-dict / dict-of-list shorthand.
        try:
            df = pd.DataFrame(df)
        except Exception:
            return df

    if df.empty:
        return df.copy()

    out = df.copy()
    for col in out.columns:
        series = out[col]
        # Object / mixed columns are the danger zone for Arrow.
        if series.dtype == object:
            out[col] = series.map(_coerce_cell).astype("string")
        else:
            # Numeric/bool/datetime columns are safe — leave alone.
            continue

    # Force any column whose values still contain non-primitive types
    # (e.g. category of dicts) to string.
    for col in out.columns:
        if out[col].dtype == object:
            try:
                out[col] = out[col].astype("string")
            except Exception:
                out[col] = out[col].map(lambda v: "" if v is None else str(v))

    return out
