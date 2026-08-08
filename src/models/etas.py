from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ETASLiteParameters:
    mu_per_day: float
    productivity: float
    alpha: float
    c_days: float
    p: float
    mc: float
    training_events: int


@dataclass(frozen=True)
class ETASLiteEstimate:
    probability: float
    expected_events: float
    background_expected: float
    triggered_expected: float
    parameters: ETASLiteParameters


def fit_etas_lite(events: pd.DataFrame, cutoff: pd.Timestamp, mc: float) -> ETASLiteParameters:
    data = events.copy()
    data["origin_time_utc"] = pd.to_datetime(data["origin_time_utc"], utc=True, errors="coerce")
    data["magnitude_comparable"] = pd.to_numeric(data["magnitude_comparable"], errors="coerce")
    data = data[
        (data["origin_time_utc"] <= cutoff)
        & (data["magnitude_comparable"] >= mc)
    ].dropna(subset=["origin_time_utc", "magnitude_comparable"]).sort_values("origin_time_utc")
    n = len(data)
    if n < 2:
        return ETASLiteParameters(0.0, 0.0, 1.0, 0.05, 1.2, float(mc), n)
    # Convert to native Python datetimes before subtraction.  Pandas Timedelta
    # is limited to roughly +/-292 years at nanosecond resolution; MEMÓRIA's
    # catalogue can span more than three centuries, so direct Timestamp
    # subtraction can overflow during long-history Model Arena replays.
    first_event = pd.Timestamp(data["origin_time_utc"].min())
    exposure = max(
        1.0,
        (cutoff.to_pydatetime() - first_event.to_pydatetime()).total_seconds() / 86400.0,
    )
    raw_rate = n / exposure
    # Conservative branching proxy from short inter-event concentration.
    native_times = [pd.Timestamp(value).to_pydatetime() for value in data["origin_time_utc"]]
    intervals = np.asarray(
        [
            (current - previous).total_seconds() / 86400.0
            for previous, current in zip(native_times[:-1], native_times[1:])
        ],
        dtype=float,
    )
    short_fraction = float(np.mean(intervals <= 7.0)) if intervals.size else 0.0
    branching = float(np.clip(short_fraction, 0.05, 0.75))
    mu = raw_rate * (1.0 - branching)
    mean_productivity = branching * raw_rate
    productivity = mean_productivity / max(raw_rate, 1e-9)
    return ETASLiteParameters(
        mu_per_day=float(mu),
        productivity=float(np.clip(productivity, 0.01, 0.8)),
        alpha=0.8,
        c_days=0.05,
        p=1.2,
        mc=float(mc),
        training_events=n,
    )


def forecast_etas_lite(
    events: pd.DataFrame,
    cutoff: str | pd.Timestamp,
    horizon_days: int,
    threshold_magnitude: float,
) -> ETASLiteEstimate:
    cutoff = pd.to_datetime(cutoff, utc=True)
    params = fit_etas_lite(events, cutoff, threshold_magnitude)
    data = events.copy()
    data["origin_time_utc"] = pd.to_datetime(data["origin_time_utc"], utc=True, errors="coerce")
    data["magnitude_comparable"] = pd.to_numeric(data["magnitude_comparable"], errors="coerce")
    recent = data[
        (data["origin_time_utc"] <= cutoff)
        & (data["magnitude_comparable"] >= threshold_magnitude)
        & (data["origin_time_utc"] >= cutoff - pd.Timedelta(days=365))
    ].dropna(subset=["origin_time_utc", "magnitude_comparable"])
    background = params.mu_per_day * horizon_days
    triggered = 0.0
    for _, event in recent.iterrows():
        event_time = pd.Timestamp(event["origin_time_utc"])
        age = max(
            0.0,
            (cutoff.to_pydatetime() - event_time.to_pydatetime()).total_seconds() / 86400.0,
        )
        productivity = params.productivity * np.exp(params.alpha * (float(event["magnitude_comparable"]) - threshold_magnitude))
        # Integral of Omori-like kernel over forecast horizon.
        c = params.c_days; p = params.p
        if abs(p - 1.0) < 1e-8:
            integral = np.log((age + c + horizon_days)/(age + c))
        else:
            integral = ((age+c+horizon_days)**(1-p) - (age+c)**(1-p))/(1-p)
        triggered += max(0.0, productivity * integral)
    expected = max(0.0, background + triggered)
    probability = float(1.0 - np.exp(-expected))
    return ETASLiteEstimate(probability, float(expected), float(background), float(triggered), params)
