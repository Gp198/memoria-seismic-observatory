from __future__ import annotations

import hashlib
from typing import Iterable

import pandas as pd

EVENT_COLUMNS = [
    "event_id_memoria",
    "source_event_id",
    "source",
    "origin_time_utc",
    "latitude",
    "longitude",
    "depth_km",
    "magnitude_value",
    "magnitude_type",
    "magnitude_original_value",
    "magnitude_original_type",
    "magnitude_comparable",
    "magnitude_homogenization_method",
    "magnitude_conversion_equation",
    "magnitude_conversion_uncertainty",
    "magnitude_homogenization_status",
    "intensity_max",
    "location_text",
    "felt",
    "location_uncertainty_km",
    "magnitude_uncertainty",
    "tectonic_domain",
    "domain_confidence",
    "historical_quality",
    "quality_score",
    "record_status",
    "source_url",
    "source_file",
    "duplicate_group_id",
    "is_preferred_record",
    "cluster_id",
    "cluster_role",
    "is_background_event",
    "declustering_method",
    "declustering_eligible",
    "declustering_exclusion_reason",
    "ingested_at_utc",
]

STRING_COLUMNS = [
    "event_id_memoria",
    "source_event_id",
    "source",
    "magnitude_type",
    "magnitude_original_type",
    "magnitude_homogenization_method",
    "magnitude_conversion_equation",
    "magnitude_homogenization_status",
    "intensity_max",
    "location_text",
    "tectonic_domain",
    "historical_quality",
    "record_status",
    "source_url",
    "source_file",
    "duplicate_group_id",
    "cluster_id",
    "cluster_role",
    "declustering_method",
    "declustering_exclusion_reason",
]

NUMERIC_COLUMNS = [
    "latitude",
    "longitude",
    "depth_km",
    "magnitude_value",
    "magnitude_original_value",
    "magnitude_comparable",
    "magnitude_conversion_uncertainty",
    "location_uncertainty_km",
    "magnitude_uncertainty",
    "domain_confidence",
    "quality_score",
]

BOOLEAN_COLUMNS = [
    "felt",
    "is_preferred_record",
    "is_background_event",
    "declustering_eligible",
]


def stable_event_id(
    source: str,
    source_event_id: str | None,
    origin_time: object,
    latitude: object,
    longitude: object,
) -> str:
    raw = "|".join(
        [
            str(source or ""),
            str(source_event_id or ""),
            str(origin_time or ""),
            str(latitude or ""),
            str(longitude or ""),
        ]
    )
    return "MEM-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16].upper()


def _normalise_string_series(series: pd.Series) -> pd.Series:
    """Return a true pandas StringDtype series without converting nulls to text."""
    return series.astype("string")



def _apply_physical_plausibility(result: pd.DataFrame) -> pd.DataFrame:
    """Replace catalogue sentinels and physically implausible values with nulls.

    Historical catalogues commonly use values such as -99 or 999 for unknown
    quantities. Keeping those values would corrupt histograms, energies and
    similarity features.
    """
    bounds = {
        "latitude": (-90.0, 90.0),
        "longitude": (-180.0, 180.0),
        "depth_km": (-10.0, 800.0),
        "magnitude_value": (-3.0, 10.5),
        "magnitude_comparable": (-3.0, 10.5),
        "magnitude_original_value": (-3.0, 10.5),
        "magnitude_conversion_uncertainty": (0.0, 10.0),
        "location_uncertainty_km": (0.0, 5000.0),
        "magnitude_uncertainty": (0.0, 10.0),
        "domain_confidence": (0.0, 1.0),
        "quality_score": (0.0, 1.0),
    }
    for column, (minimum, maximum) in bounds.items():
        if column in result.columns:
            invalid = result[column].notna() & ~result[column].between(
                minimum, maximum, inclusive="both"
            )
            result.loc[invalid, column] = pd.NA
    return result

def ensure_event_schema(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in EVENT_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA

    result = result[EVENT_COLUMNS]

    result["origin_time_utc"] = pd.to_datetime(
        result["origin_time_utc"], utc=True, errors="coerce"
    )
    result["ingested_at_utc"] = pd.to_datetime(
        result["ingested_at_utc"], utc=True, errors="coerce"
    )

    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("Float64")

    result = _apply_physical_plausibility(result)

    for column in STRING_COLUMNS:
        result[column] = _normalise_string_series(result[column])

    for column in BOOLEAN_COLUMNS:
        result[column] = result[column].astype("boolean")

    # Deterministic flags and provenance fallbacks for downstream filters.
    result["is_preferred_record"] = result["is_preferred_record"].fillna(True)
    result["is_background_event"] = result["is_background_event"].fillna(False)
    result["magnitude_original_value"] = result["magnitude_original_value"].fillna(
        result["magnitude_value"]
    )
    result["magnitude_original_type"] = result["magnitude_original_type"].fillna(
        result["magnitude_type"]
    )

    return result


def concatenate_events(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    available = [
        ensure_event_schema(frame)
        for frame in frames
        if frame is not None and not frame.empty
    ]
    if not available:
        return ensure_event_schema(pd.DataFrame(columns=EVENT_COLUMNS))
    return ensure_event_schema(pd.concat(available, ignore_index=True))
