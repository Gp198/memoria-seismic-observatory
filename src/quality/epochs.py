from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.quality.completeness import estimate_magnitude_completeness


@dataclass(frozen=True)
class ObservationEpoch:
    key: str
    label: str
    start_year: int
    end_year: int | None
    minimum_comparable_magnitude: float


OBSERVATION_EPOCHS = (
    ObservationEpoch(
        "historical_pre_instrumental",
        "Histórica pré-instrumental",
        1000,
        1899,
        5.0,
    ),
    ObservationEpoch(
        "early_instrumental",
        "Instrumental inicial",
        1900,
        1963,
        4.0,
    ),
    ObservationEpoch(
        "modern_network",
        "Rede instrumental moderna",
        1964,
        2007,
        3.0,
    ),
    ObservationEpoch(
        "contemporary_network",
        "Período instrumental contemporâneo",
        2008,
        None,
        1.5,
    ),
)

EPOCH_BY_KEY = {epoch.key: epoch for epoch in OBSERVATION_EPOCHS}


def observation_epoch_for_year(year: int) -> ObservationEpoch:
    for epoch in OBSERVATION_EPOCHS:
        if year < epoch.start_year:
            continue
        if epoch.end_year is None or year <= epoch.end_year:
            return epoch
    return OBSERVATION_EPOCHS[0]


def observation_epoch_for_timestamp(value: object) -> ObservationEpoch:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return OBSERVATION_EPOCHS[-1]
    return observation_epoch_for_year(int(timestamp.year))


def epoch_start_timestamp(epoch_key: str) -> pd.Timestamp:
    epoch = EPOCH_BY_KEY[epoch_key]
    return pd.Timestamp(f"{epoch.start_year:04d}-01-01", tz="UTC")


def assign_observation_epoch(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    dates = pd.to_datetime(
        result["origin_time_utc"],
        utc=True,
        errors="coerce",
    )
    epochs = dates.map(
        lambda value: (
            observation_epoch_for_year(int(value.year))
            if pd.notna(value)
            else OBSERVATION_EPOCHS[-1]
        )
    )
    result["observation_epoch"] = epochs.map(lambda epoch: epoch.key)
    result["observation_epoch_label"] = epochs.map(lambda epoch: epoch.label)
    return result


def estimate_domain_epoch_thresholds(
    frame: pd.DataFrame,
    minimum_events: int = 30,
) -> dict[tuple[str, str], dict[str, float | int | str | None]]:
    events = assign_observation_epoch(frame)
    thresholds: dict[
        tuple[str, str],
        dict[str, float | int | str | None],
    ] = {}

    for (domain, epoch_key), group in events.groupby(
        ["tectonic_domain", "observation_epoch"],
        dropna=False,
    ):
        if pd.isna(domain):
            continue
        epoch = EPOCH_BY_KEY[str(epoch_key)]
        magnitudes = pd.to_numeric(
            group["magnitude_comparable"],
            errors="coerce",
        ).dropna()
        estimate = estimate_magnitude_completeness(
            magnitudes,
            minimum_events=minimum_events,
        )
        estimated_mc = estimate.mc
        threshold = max(
            epoch.minimum_comparable_magnitude,
            float(estimated_mc)
            if estimated_mc is not None
            else epoch.minimum_comparable_magnitude,
        )
        thresholds[(str(domain), str(epoch_key))] = {
            "epoch_key": epoch.key,
            "epoch_label": epoch.label,
            "policy_floor": epoch.minimum_comparable_magnitude,
            "estimated_mc": estimated_mc,
            "comparison_threshold": float(round(threshold, 1)),
            "epoch_event_count": int(len(group)),
            "epoch_magnitude_count": int(len(magnitudes)),
        }

    return thresholds
