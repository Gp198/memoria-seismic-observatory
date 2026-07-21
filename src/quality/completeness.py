from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CompletenessEstimate:
    mc: float | None
    event_count: int
    bin_width: float
    method: str = "maximum_curvature"
    sufficient_data: bool = False


def estimate_magnitude_completeness(
    magnitudes: pd.Series | list[float],
    bin_width: float = 0.1,
    minimum_events: int = 50,
) -> CompletenessEstimate:
    values = pd.to_numeric(pd.Series(magnitudes), errors="coerce").dropna().to_numpy()
    if len(values) < minimum_events:
        return CompletenessEstimate(
            mc=None,
            event_count=len(values),
            bin_width=bin_width,
            sufficient_data=False,
        )
    lower = np.floor(values.min() / bin_width) * bin_width
    upper = np.ceil(values.max() / bin_width) * bin_width + bin_width
    bins = np.arange(lower, upper + bin_width / 2, bin_width)
    counts, edges = np.histogram(values, bins=bins)
    if counts.sum() == 0:
        return CompletenessEstimate(None, len(values), bin_width, sufficient_data=False)
    peak_index = int(np.argmax(counts))
    mc = round(float(edges[peak_index] + bin_width / 2), 2)
    return CompletenessEstimate(
        mc=mc,
        event_count=len(values),
        bin_width=bin_width,
        sufficient_data=True,
    )


def add_epoch_completeness(
    frame: pd.DataFrame,
    epoch_years: int = 10,
    minimum_events: int = 50,
) -> pd.DataFrame:
    events = frame.copy()
    events["origin_time_utc"] = pd.to_datetime(events["origin_time_utc"], utc=True, errors="coerce")
    events["epoch_start_year"] = (
        events["origin_time_utc"].dt.year // epoch_years * epoch_years
    )
    estimates = []
    for (domain, epoch), group in events.groupby(["tectonic_domain", "epoch_start_year"], dropna=False):
        estimate = estimate_magnitude_completeness(
            group["magnitude_comparable"], minimum_events=minimum_events
        )
        estimates.append(
            {
                "tectonic_domain": domain,
                "epoch_start_year": epoch,
                "catalogue_completeness_mc": estimate.mc,
                "completeness_event_count": estimate.event_count,
                "completeness_sufficient_data": estimate.sufficient_data,
            }
        )
    return pd.DataFrame(estimates)
