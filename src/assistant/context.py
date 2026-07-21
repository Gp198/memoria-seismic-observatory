from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.assistant.knowledge import APP_KNOWLEDGE


def _safe_number(value: Any, digits: int = 4) -> float | int | None:
    try:
        if value is None or pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(float(value)):
            return None
        return round(float(value), digits)
    return None


def _safe_timestamp(value: Any) -> str | None:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp.isoformat()


def _normalise(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _normalise(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalise(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return _safe_timestamp(value)
    numeric = _safe_number(value)
    if numeric is not None:
        return numeric
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (str, bool)):
        return value
    return str(value)


def _latest_fingerprint(domain_fingerprints: pd.DataFrame) -> dict[str, Any]:
    if domain_fingerprints.empty:
        return {"available": False}
    latest = domain_fingerprints.sort_values("window_end").iloc[-1]
    keys = [
        "window_start",
        "window_end",
        "window_days",
        "event_count",
        "comparable_event_count",
        "event_rate_per_30d",
        "comparable_event_rate_per_30d",
        "maximum_magnitude",
        "mean_magnitude",
        "median_depth_km",
        "spatial_dispersion_km",
        "data_quality_score",
        "comparison_epoch_label",
        "comparison_magnitude_threshold",
        "comparable_percentile_event_rate",
        "comparable_percentile_ci_lower",
        "comparable_percentile_ci_upper",
        "comparable_effective_sample_size",
        "comparable_reference_windows",
        "catalogue_completeness_mc",
    ]
    result = {"available": True}
    for key in keys:
        if key in latest.index:
            result[key] = _normalise(latest.get(key))
    return result


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame.columns:
        return frame[name]
    return pd.Series(index=frame.index, dtype="object")


def _event_summary(domain_events: pd.DataFrame) -> dict[str, Any]:
    if domain_events.empty:
        return {"available": False, "event_count": 0}
    dates = pd.to_datetime(
        _column(domain_events, "origin_time_utc"), utc=True, errors="coerce"
    ).dropna()
    magnitudes = pd.to_numeric(
        _column(domain_events, "magnitude_comparable"), errors="coerce"
    ).dropna()
    depths = pd.to_numeric(
        _column(domain_events, "depth_km"), errors="coerce"
    ).dropna()
    source_counts = (
        _column(domain_events, "source")
        .astype("string")
        .fillna("UNKNOWN")
        .value_counts()
        .head(6)
        .to_dict()
    )
    return {
        "available": True,
        "event_count": int(len(domain_events)),
        "first_event": _safe_timestamp(dates.min()) if not dates.empty else None,
        "last_event": _safe_timestamp(dates.max()) if not dates.empty else None,
        "maximum_magnitude": _safe_number(magnitudes.max()) if not magnitudes.empty else None,
        "median_magnitude": _safe_number(magnitudes.median()) if not magnitudes.empty else None,
        "median_depth_km": _safe_number(depths.median()) if not depths.empty else None,
        "sources": _normalise(source_counts),
    }


def build_assistant_context(
    *,
    page: str,
    selected_domain: str,
    catalogue_label: str,
    catalogue_mode: str,
    magnitude_policy_label: str,
    magnitude_policy: str,
    selected_window: int,
    minimum_map_magnitude: float,
    domain_events: pd.DataFrame,
    domain_fingerprints: pd.DataFrame,
    validated_coverage: float | None,
    page_details: Mapping[str, Any] | None = None,
    app_version: str = "",
) -> dict[str, Any]:
    """Create a compact, aggregate-only context for the explanatory assistant.

    Raw catalogue rows, coordinates and API credentials are deliberately excluded.
    """
    context = {
        "application": {
            "name": "MEMÓRIA — Portuguese Seismic Memory Observatory",
            "version": app_version,
            "creator": "Gonçalo Pedro",
            "institutional_status": "Projeto experimental independente",
            "purpose": APP_KNOWLEDGE["purpose"],
            "current_page": page,
            "page_function": APP_KNOWLEDGE["pages"].get(page),
        },
        "authoritative_project_identity": APP_KNOWLEDGE["identity"],
        "selection": {
            "tectonic_domain": selected_domain,
            "catalogue_label": catalogue_label,
            "catalogue_mode": catalogue_mode,
            "magnitude_policy_label": magnitude_policy_label,
            "magnitude_policy": magnitude_policy,
            "analytical_window_days": int(selected_window),
            "minimum_map_magnitude": float(minimum_map_magnitude),
            "validated_magnitude_coverage": _safe_number(validated_coverage),
        },
        "domain_catalogue_summary": _event_summary(domain_events),
        "current_fingerprint": _latest_fingerprint(domain_fingerprints),
        "page_details": _normalise(page_details or {}),
        "concept_guide": APP_KNOWLEDGE["concepts"],
        "scientific_boundaries": APP_KNOWLEDGE["boundaries"],
        "privacy": (
            "O contexto enviado contém apenas métricas agregadas e opções da interface; "
            "não contém linhas brutas do catálogo, coordenadas individuais nem chaves."
        ),
    }
    return _normalise(context)


def context_to_text(context: Mapping[str, Any], max_characters: int = 14000) -> str:
    text = json.dumps(
        _normalise(context),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    if len(text) <= max_characters:
        return text
    compact = json.dumps(
        _normalise(context),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(compact) <= max_characters:
        return compact
    return json.dumps(
        {
            "context_truncated": True,
            "context_prefix": compact[: max(0, max_characters - 90)],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )[:max_characters]
