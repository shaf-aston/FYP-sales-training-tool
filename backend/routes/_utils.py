"""Shared helpers for route-layer response serialization."""

from __future__ import annotations

from numbers import Real


def safe_latency_ms(value) -> float | None:
    """Round latency values for JSON responses without crashing on None."""
    if value is None:
        return None
    if isinstance(value, Real):
        return round(float(value), 1)
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def sum_latency_ms(*values) -> float | None:
    """Sum latency values only when every component is present and numeric."""
    numeric_values = []
    for value in values:
        if value is None:
            return None
        if isinstance(value, Real):
            numeric_values.append(float(value))
            continue
        try:
            numeric_values.append(float(value))
        except (TypeError, ValueError):
            return None

    if not numeric_values:
        return None
    return round(sum(numeric_values), 1)
