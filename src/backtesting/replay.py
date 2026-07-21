from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.quality.deduplication import preferred_events
from src.quality.declustering import select_catalogue_mode
from src.quality.magnitude import select_magnitude_policy
from src.quality.epochs import (
    epoch_start_timestamp,
    observation_epoch_for_timestamp,
)
from src.similarity.nearest_states import SimilarityResult, nearest_states


@dataclass
class BaselineEstimate:
    epoch_key: str
    epoch_label: str
    training_start: pd.Timestamp
    training_end: pd.Timestamp
    exposure_days: float
    threshold_event_count: int
    empirical_window_count: int
    empirical_positive_windows: int
    empirical_probability: float
    poisson_lambda_per_day: float
    poisson_probability: float


@dataclass
class ReplayResult:
    cutoff: pd.Timestamp
    target_domain: str
    window_days: int
    threshold_magnitude: float
    horizon_days: int
    analogue_probability: float
    historical_rate_probability: float
    poisson_probability: float
    observed_outcome: bool
    brier_analogue: float
    brier_historical: float
    brier_poisson: float
    similarity: SimilarityResult
    neighbour_outcomes: pd.DataFrame
    baseline: BaselineEstimate


def _future_outcome(events, domain, start, horizon_days, threshold):
    end = start + pd.Timedelta(days=horizon_days)
    subset = events[
        (events["tectonic_domain"] == domain)
        & (events["origin_time_utc"] > start)
        & (events["origin_time_utc"] <= end)
        & (
            pd.to_numeric(
                events["magnitude_comparable"], errors="coerce"
            )
            >= threshold
        )
    ]
    return not subset.empty


def _baseline_estimate(events, domain, cutoff, threshold, horizon_days):
    epoch = observation_epoch_for_timestamp(cutoff)
    history = events[
        (events["tectonic_domain"] == domain)
        & (events["origin_time_utc"] <= cutoff)
    ].copy()
    history["origin_time_utc"] = pd.to_datetime(
        history["origin_time_utc"], utc=True, errors="coerce"
    )
    history = history.dropna(subset=["origin_time_utc"])
    epoch_start = epoch_start_timestamp(epoch.key)
    history = history[history["origin_time_utc"] >= epoch_start]

    if history.empty:
        return BaselineEstimate(
            epoch.key, epoch.label, cutoff, cutoff, 0.0, 0, 0, 0,
            0.0, 0.0, 0.0
        )

    training_start = max(
        epoch_start,
        history["origin_time_utc"].min().normalize(),
    )
    exposure_days = max(
        0.0,
        (
            cutoff.to_pydatetime()
            - training_start.to_pydatetime()
        ).total_seconds()
        / 86400.0,
    )
    threshold_events = history[
        pd.to_numeric(
            history["magnitude_comparable"], errors="coerce"
        )
        >= threshold
    ]
    event_count = int(len(threshold_events))
    windows = int(exposure_days // horizon_days)

    if windows > 0:
        empirical_start = cutoff - pd.Timedelta(
            days=windows * horizon_days
        )
        offsets = (
            threshold_events["origin_time_utc"] - empirical_start
        ).dt.total_seconds() / 86400.0
        valid = offsets[
            (offsets > 0)
            & (offsets <= windows * horizon_days)
        ]
        positive_bins = {
            min(windows - 1, int(offset // horizon_days))
            for offset in valid
        }
        positive = len(positive_bins)
        empirical_probability = positive / windows
    else:
        positive = 0
        empirical_probability = 0.0

    lambda_per_day = (
        event_count / exposure_days if exposure_days > 0 else 0.0
    )
    poisson_probability = float(
        1 - np.exp(-lambda_per_day * horizon_days)
    )

    return BaselineEstimate(
        epoch.key,
        epoch.label,
        training_start,
        cutoff,
        exposure_days,
        event_count,
        windows,
        positive,
        float(empirical_probability),
        float(lambda_per_day),
        poisson_probability,
    )


def _historical_rate(events, domain, cutoff, threshold, horizon_days):
    return _baseline_estimate(
        events, domain, cutoff, threshold, horizon_days
    ).empirical_probability


def run_replay(
    events,
    fingerprints,
    cutoff,
    domain,
    window_days=90,
    threshold_magnitude=4.0,
    horizon_days=30,
    k=5,
    exclusion_days=365,
    diversity_days=None,
    family_gap_days=None,
    family_buffer_days=None,
    family_method="fixed",
    catalogue_mode="complete",
    magnitude_policy="operational",
):
    cutoff_time = pd.to_datetime(cutoff, utc=True)
    clean_events = select_magnitude_policy(
        select_catalogue_mode(preferred_events(events), catalogue_mode),
        magnitude_policy,
    ).copy()
    clean_events["origin_time_utc"] = pd.to_datetime(
        clean_events["origin_time_utc"], utc=True, errors="coerce"
    )
    known_source = fingerprints.copy()
    if "catalogue_mode" in known_source.columns:
        known_source = known_source[known_source["catalogue_mode"].astype(str) == catalogue_mode]
    if "magnitude_policy" in known_source.columns:
        known_source = known_source[known_source["magnitude_policy"].astype(str) == magnitude_policy]
    known = known_source[
        pd.to_datetime(
            known_source["window_end"], utc=True, errors="coerce"
        )
        <= cutoff_time
    ].copy()
    similarity = nearest_states(
        known,
        domain,
        window_days,
        target_end=cutoff_time,
        k=k,
        exclusion_days=exclusion_days,
        diversity_days=diversity_days,
        family_gap_days=family_gap_days,
        family_buffer_days=family_buffer_days,
        strict_epoch=True,
        family_method=family_method,
    )

    rows = []
    outcomes = []
    for _, neighbour in similarity.neighbours.iterrows():
        neighbour_end = pd.to_datetime(
            neighbour["window_end"], utc=True
        )
        outcome = _future_outcome(
            clean_events[
                clean_events["origin_time_utc"] <= cutoff_time
            ],
            domain,
            neighbour_end,
            horizon_days,
            threshold_magnitude,
        )
        outcomes.append(float(outcome))
        rows.append(
            {
                "family_id": neighbour.get("family_id"),
                "family_start": neighbour.get("family_start"),
                "family_end": neighbour.get("family_end"),
                "episode_id": neighbour.get("episode_id"),
                "window_start": neighbour.get("window_start"),
                "window_end": neighbour_end,
                "similarity": neighbour["similarity"],
                "comparability_score": neighbour.get(
                    "comparability_score", 1.0
                ),
                "future_event": outcome,
                "family_method": neighbour.get("family_method", family_method),
            }
        )

    if outcomes:
        weights = (
            similarity.neighbours["similarity"].to_numpy(float)
            * similarity.neighbours[
                "comparability_score"
            ].to_numpy(float)
        )
        analogue_probability = float(
            np.average(outcomes, weights=weights)
        )
    else:
        analogue_probability = 0.0

    baseline = _baseline_estimate(
        clean_events,
        domain,
        cutoff_time,
        threshold_magnitude,
        horizon_days,
    )
    observed = _future_outcome(
        clean_events,
        domain,
        cutoff_time,
        horizon_days,
        threshold_magnitude,
    )
    actual = float(observed)

    return ReplayResult(
        cutoff_time,
        domain,
        window_days,
        threshold_magnitude,
        horizon_days,
        analogue_probability,
        baseline.empirical_probability,
        baseline.poisson_probability,
        observed,
        (analogue_probability - actual) ** 2,
        (baseline.empirical_probability - actual) ** 2,
        (baseline.poisson_probability - actual) ** 2,
        similarity,
        pd.DataFrame(rows),
        baseline,
    )


def walk_forward_backtest(
    events,
    fingerprints,
    domain,
    window_days=90,
    threshold_magnitude=4.0,
    horizon_days=30,
    start_date=None,
    frequency="90D",
    family_method="adaptive",
    catalogue_mode="complete",
    magnitude_policy="operational",
):
    source_fp = fingerprints.copy()
    if "catalogue_mode" in source_fp.columns:
        source_fp = source_fp[source_fp["catalogue_mode"].astype(str) == catalogue_mode]
    if "magnitude_policy" in source_fp.columns:
        source_fp = source_fp[source_fp["magnitude_policy"].astype(str) == magnitude_policy]
    domain_fp = source_fp[
        (source_fp["tectonic_domain"] == domain)
        & (source_fp["window_days"] == window_days)
    ].copy()
    domain_fp["window_end"] = pd.to_datetime(
        domain_fp["window_end"], utc=True
    )
    if domain_fp.empty:
        return pd.DataFrame()
    if start_date:
        earliest = pd.to_datetime(start_date, utc=True)
    else:
        dates = domain_fp["window_end"].dropna().sort_values()
        earliest = dates.iloc[
            min(len(dates) - 1, int((len(dates) - 1) * 0.4))
        ]
    latest = domain_fp["window_end"].max() - pd.Timedelta(
        days=horizon_days
    )
    rows = []
    for cutoff in pd.date_range(
        earliest, latest, freq=frequency, tz="UTC"
    ):
        try:
            result = run_replay(
                events,
                fingerprints,
                cutoff,
                domain,
                window_days,
                threshold_magnitude,
                horizon_days,
                family_gap_days=max(window_days * 8, 365),
                family_method=family_method,
                catalogue_mode=catalogue_mode,
                magnitude_policy=magnitude_policy,
            )
        except ValueError:
            continue
        rows.append(
            {
                "cutoff": result.cutoff,
                "analogue_probability": result.analogue_probability,
                "historical_rate_probability": (
                    result.historical_rate_probability
                ),
                "poisson_probability": result.poisson_probability,
                "observed_outcome": result.observed_outcome,
                "brier_analogue": result.brier_analogue,
                "brier_historical": result.brier_historical,
                "brier_poisson": result.brier_poisson,
                "baseline_epoch": result.baseline.epoch_label,
                "baseline_event_count": (
                    result.baseline.threshold_event_count
                ),
                "baseline_exposure_days": (
                    result.baseline.exposure_days
                ),
                "threshold_magnitude": float(threshold_magnitude),
                "horizon_days": int(horizon_days),
                "catalogue_mode": str(catalogue_mode),
                "magnitude_policy": str(magnitude_policy),
                "family_method": str(family_method),
            }
        )
    scores = pd.DataFrame(rows)
    if scores.empty:
        return scores
    from src.backtesting.validation import add_expanding_isotonic_calibration

    return add_expanding_isotonic_calibration(scores)


def walk_forward_grid(
    events: pd.DataFrame,
    fingerprints: pd.DataFrame,
    domain: str,
    window_days: int = 90,
    thresholds: tuple[float, ...] = (3.5, 4.0, 4.5, 5.0),
    horizons: tuple[int, ...] = (7, 30, 90),
    frequency: str = "60D",
    family_method: str = "adaptive",
    catalogue_mode: str = "complete",
    magnitude_policy: str = "operational",
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for threshold in thresholds:
        for horizon in horizons:
            scores = walk_forward_backtest(
                events,
                fingerprints,
                domain,
                window_days=window_days,
                threshold_magnitude=float(threshold),
                horizon_days=int(horizon),
                frequency=frequency,
                family_method=family_method,
                catalogue_mode=catalogue_mode,
                magnitude_policy=magnitude_policy,
            )
            if scores.empty:
                continue
            frames.append(scores)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(
        ["threshold_magnitude", "horizon_days", "cutoff"]
    ).reset_index(drop=True)
