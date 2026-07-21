from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from src.common import haversine_km, seismic_energy_joule
from src.quality.completeness import estimate_magnitude_completeness
from src.quality.deduplication import preferred_events
from src.quality.declustering import select_catalogue_mode
from src.quality.magnitude import select_magnitude_policy
from src.quality.epochs import (
    assign_observation_epoch,
    estimate_domain_epoch_thresholds,
    observation_epoch_for_timestamp,
)
from bisect import bisect_right, insort

from src.quality.statistics import wilson_interval

FINGERPRINT_FEATURES = [
    "comparable_event_count",
    "comparable_event_rate_per_30d",
    "maximum_magnitude",
    "mean_magnitude",
    "median_depth_km",
    "depth_std_km",
    "spatial_dispersion_km",
    "log10_total_energy_j",
    "days_since_previous_m3",
    "catalogue_completeness_mc",
    "data_quality_score",
]


def _spatial_dispersion(group: pd.DataFrame) -> float:
    valid = group.dropna(subset=["latitude", "longitude"])
    if len(valid) < 2:
        return 0.0
    centroid_lat = valid["latitude"].mean()
    centroid_lon = valid["longitude"].mean()
    distances = haversine_km(
        valid["latitude"].to_numpy(),
        valid["longitude"].to_numpy(),
        centroid_lat,
        centroid_lon,
    )
    return float(np.median(distances))


def _coverage_ratio(group: pd.DataFrame, columns: list[str]) -> float:
    if group.empty:
        return np.nan
    available = pd.Series(True, index=group.index)
    for column in columns:
        if column not in group.columns:
            return 0.0
        available &= group[column].notna()
    return float(available.mean())


def _source_profile(group: pd.DataFrame) -> dict[str, float | str]:
    sources = (
        group.get("source", pd.Series("", index=group.index))
        .astype("string")
        .fillna("OTHER")
        .str.upper()
    )
    total = max(len(sources), 1)
    shares = {
        "source_share_ipma": float((sources == "IPMA").sum() / total),
        "source_share_isc": float((sources == "ISC").sum() / total),
        "source_share_ahead": float((sources == "AHEAD").sum() / total),
    }
    shares["source_share_other"] = max(
        0.0,
        1.0 - sum(shares.values()),
    )

    values = np.asarray(
        [value for value in shares.values() if value > 0],
        dtype=float,
    )
    if len(values) <= 1:
        diversity = 0.0
    else:
        entropy = -float(np.sum(values * np.log(values)))
        diversity = entropy / np.log(4.0)

    counts = sources.value_counts()
    dominant = str(counts.index[0]) if not counts.empty else "UNKNOWN"

    return {
        **shares,
        "source_diversity_score": float(np.clip(diversity, 0.0, 1.0)),
        "dominant_source": dominant,
    }


def _window_fingerprint(
    all_domain_events: pd.DataFrame,
    window_events: pd.DataFrame,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    window_days: int,
    comparison_threshold: float,
    epoch_metadata: dict[str, object],
) -> dict[str, float | int | str | pd.Timestamp]:
    all_magnitudes = pd.to_numeric(
        window_events["magnitude_comparable"],
        errors="coerce",
    )
    comparable_events = window_events.loc[
        all_magnitudes >= comparison_threshold
    ].copy()
    magnitudes = pd.to_numeric(
        comparable_events["magnitude_comparable"],
        errors="coerce",
    ).dropna()
    depths = pd.to_numeric(
        comparable_events["depth_km"],
        errors="coerce",
    ).dropna()

    completeness = estimate_magnitude_completeness(
        all_magnitudes.dropna(),
        minimum_events=20,
    )
    prior_m3 = all_domain_events[
        (all_domain_events["origin_time_utc"] < window_end)
        & (
            pd.to_numeric(
                all_domain_events["magnitude_comparable"],
                errors="coerce",
            )
            >= max(3.0, comparison_threshold)
        )
    ]
    if prior_m3.empty:
        days_since_m3 = np.nan
    else:
        previous = prior_m3["origin_time_utc"].max()
        days_since_m3 = max(
            0.0,
            (window_end - previous).total_seconds() / 86400,
        )

    if magnitudes.empty:
        total_energy_log = np.nan
    else:
        total_energy = float(seismic_energy_joule(magnitudes).sum())
        total_energy_log = (
            float(np.log10(total_energy))
            if total_energy > 0
            else np.nan
        )

    return {
        "window_start": window_start,
        "window_end": window_end,
        "window_days": window_days,
        "comparison_epoch": str(epoch_metadata["epoch_key"]),
        "comparison_epoch_label": str(epoch_metadata["epoch_label"]),
        "comparison_magnitude_threshold": float(comparison_threshold),
        "epoch_catalogue_mc": epoch_metadata.get("estimated_mc"),
        "epoch_event_count": int(epoch_metadata["epoch_event_count"]),
        "event_count": int(len(window_events)),
        "event_rate_per_30d": float(len(window_events) * 30 / window_days),
        "comparable_event_count": int(len(comparable_events)),
        "comparable_event_rate_per_30d": float(
            len(comparable_events) * 30 / window_days
        ),
        "maximum_magnitude": (
            float(magnitudes.max()) if not magnitudes.empty else np.nan
        ),
        "mean_magnitude": (
            float(magnitudes.mean()) if not magnitudes.empty else np.nan
        ),
        "median_depth_km": (
            float(depths.median()) if not depths.empty else np.nan
        ),
        "depth_std_km": (
            float(depths.std(ddof=0)) if len(depths) > 1 else 0.0
        ),
        "spatial_dispersion_km": _spatial_dispersion(comparable_events),
        "log10_total_energy_j": total_energy_log,
        "days_since_previous_m3": days_since_m3,
        "catalogue_completeness_mc": completeness.mc,
        "data_quality_score": (
            float(
                pd.to_numeric(
                    window_events["quality_score"],
                    errors="coerce",
                ).mean()
            )
            if not window_events.empty
            else np.nan
        ),
        "magnitude_coverage_ratio": _coverage_ratio(
            window_events,
            ["magnitude_comparable"],
        ),
        "depth_coverage_ratio": _coverage_ratio(
            comparable_events,
            ["depth_km"],
        ),
        "location_coverage_ratio": _coverage_ratio(
            comparable_events,
            ["latitude", "longitude"],
        ),
        **_source_profile(window_events),
    }


def _running_percentiles(
    result: pd.DataFrame,
    group_columns: list[str],
    value_column: str,
    output_prefix: str,
    minimum_reference_windows: int,
    window_days: int,
    step_days: int,
) -> None:
    percentile_column = f"{output_prefix}_percentile_event_rate"
    count_column = f"{output_prefix}_reference_windows"
    effective_column = f"{output_prefix}_effective_sample_size"
    lower_column = f"{output_prefix}_percentile_ci_lower"
    upper_column = f"{output_prefix}_percentile_ci_upper"
    overlap_column = f"{output_prefix}_overlap_factor"
    autocorrelation_column = f"{output_prefix}_lag1_autocorrelation"

    result[percentile_column] = np.nan
    result[count_column] = 0
    result[effective_column] = np.nan
    result[lower_column] = np.nan
    result[upper_column] = np.nan
    result[overlap_column] = 1
    result[autocorrelation_column] = np.nan

    overlap_factor = max(1, int(np.ceil(window_days / max(step_days, 1))))

    for _, indices in result.groupby(group_columns).groups.items():
        ordered = result.loc[indices].sort_values("window_end")
        sorted_values: list[float] = []
        previous_value: float | None = None
        pair_count = 0
        sum_left = 0.0
        sum_right = 0.0
        sum_left_sq = 0.0
        sum_right_sq = 0.0
        sum_product = 0.0

        for row_index, raw_value in zip(
            ordered.index,
            pd.to_numeric(ordered[value_column], errors="coerce"),
        ):
            value = float(raw_value) if np.isfinite(raw_value) else np.nan
            reference_count = len(sorted_values)
            result.at[row_index, count_column] = reference_count
            result.at[row_index, overlap_column] = overlap_factor

            rho1 = np.nan
            if pair_count >= 2:
                numerator = (
                    pair_count * sum_product - sum_left * sum_right
                )
                left_variance = (
                    pair_count * sum_left_sq - sum_left * sum_left
                )
                right_variance = (
                    pair_count * sum_right_sq - sum_right * sum_right
                )
                denominator = np.sqrt(
                    max(left_variance, 0.0) * max(right_variance, 0.0)
                )
                if denominator > 0:
                    rho1 = float(
                        np.clip(numerator / denominator, -0.99, 0.99)
                    )
            result.at[row_index, autocorrelation_column] = rho1

            if reference_count > 0:
                non_overlap_bound = reference_count / overlap_factor
                if np.isfinite(rho1) and rho1 > 0:
                    autocorrelation_bound = (
                        reference_count * (1.0 - rho1) / (1.0 + rho1)
                    )
                else:
                    autocorrelation_bound = float(reference_count)
                effective = float(
                    np.clip(
                        min(
                            float(reference_count),
                            max(1.0, non_overlap_bound),
                            max(1.0, autocorrelation_bound),
                        ),
                        1.0,
                        float(reference_count),
                    )
                )
            else:
                effective = 0.0
            result.at[row_index, effective_column] = effective

            if (
                reference_count >= minimum_reference_windows
                and np.isfinite(value)
            ):
                percentile = bisect_right(sorted_values, value) / reference_count
                lower, upper = wilson_interval(percentile, effective)
                result.at[row_index, percentile_column] = percentile
                result.at[row_index, lower_column] = lower
                result.at[row_index, upper_column] = upper

            if np.isfinite(value):
                if previous_value is not None:
                    pair_count += 1
                    sum_left += previous_value
                    sum_right += value
                    sum_left_sq += previous_value * previous_value
                    sum_right_sq += value * value
                    sum_product += previous_value * value
                previous_value = value
                insort(sorted_values, value)


def build_fingerprints(
    frame: pd.DataFrame,
    window_days: Iterable[int] = (30, 90, 365),
    step_days: int = 7,
    minimum_window_events: int = 1,
    minimum_reference_windows: int = 10,
    catalogue_mode: str = "complete",
    magnitude_policy: str = "operational",
) -> pd.DataFrame:
    events = select_magnitude_policy(
        select_catalogue_mode(preferred_events(frame), catalogue_mode),
        magnitude_policy,
    ).copy()
    events["origin_time_utc"] = pd.to_datetime(
        events["origin_time_utc"],
        utc=True,
        errors="coerce",
    )
    events = events.dropna(
        subset=["origin_time_utc", "tectonic_domain"],
    )
    events = assign_observation_epoch(events)
    epoch_thresholds = estimate_domain_epoch_thresholds(events)
    rows: list[dict[str, object]] = []

    for domain, domain_group in events.groupby("tectonic_domain"):
        domain_group = domain_group.sort_values(
            "origin_time_utc"
        ).reset_index(drop=True)
        if domain_group.empty:
            continue

        for epoch_key, group in domain_group.groupby(
            "observation_epoch", sort=False
        ):
            group = group.sort_values("origin_time_utc").reset_index(drop=True)
            if group.empty:
                continue
            epoch = observation_epoch_for_timestamp(
                group["origin_time_utc"].iloc[-1]
            )
            metadata = epoch_thresholds.get(
                (str(domain), str(epoch_key)),
                {
                    "epoch_key": epoch.key,
                    "epoch_label": epoch.label,
                    "estimated_mc": None,
                    "comparison_threshold": (
                        epoch.minimum_comparable_magnitude
                    ),
                    "epoch_event_count": int(len(group)),
                },
            )
            event_times = group["origin_time_utc"].to_numpy()
            first_date = group["origin_time_utc"].min().normalize()
            last_date = group["origin_time_utc"].max().normalize()

            for days in window_days:
                first_end = first_date + pd.Timedelta(days=int(days) - 1)
                if first_end > last_date:
                    continue
                window_ends = pd.date_range(
                    first_end,
                    last_date,
                    freq=f"{step_days}D",
                    tz="UTC",
                )
                if len(window_ends) == 0:
                    continue
                window_starts = window_ends - pd.Timedelta(
                    days=int(days) - 1
                )
                exclusive_ends = window_ends + pd.Timedelta(days=1)
                left_positions = np.searchsorted(
                    event_times,
                    window_starts.to_numpy(),
                    side="left",
                )
                right_positions = np.searchsorted(
                    event_times,
                    exclusive_ends.to_numpy(),
                    side="left",
                )
                eligible = (
                    right_positions - left_positions
                ) >= minimum_window_events

                for window_start, window_end, left, right in zip(
                    window_starts[eligible],
                    window_ends[eligible],
                    left_positions[eligible],
                    right_positions[eligible],
                ):
                    selected = group.iloc[int(left):int(right)]
                    fingerprint = _window_fingerprint(
                        group,
                        selected,
                        window_start,
                        window_end,
                        int(days),
                        float(metadata["comparison_threshold"]),
                        metadata,
                    )
                    fingerprint["tectonic_domain"] = domain
                    fingerprint["catalogue_mode"] = catalogue_mode
                    fingerprint["magnitude_policy"] = magnitude_policy
                    rows.append(fingerprint)

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    result = result.sort_values(
        ["catalogue_mode", "magnitude_policy", "tectonic_domain", "window_days", "window_end"]
    ).reset_index(drop=True)

    for days in sorted(set(int(value) for value in window_days)):
        mask = result["window_days"] == days
        subset = result.loc[mask].copy()
        _running_percentiles(
            subset,
            ["catalogue_mode", "magnitude_policy", "tectonic_domain", "window_days"],
            "event_rate_per_30d",
            "historical",
            minimum_reference_windows,
            window_days=days,
            step_days=step_days,
        )
        _running_percentiles(
            subset,
            ["catalogue_mode", "magnitude_policy", "tectonic_domain", "window_days", "comparison_epoch"],
            "comparable_event_rate_per_30d",
            "comparable",
            minimum_reference_windows,
            window_days=days,
            step_days=step_days,
        )
        uncertainty_columns = [
            column
            for column in subset.columns
            if column.startswith("historical_")
            or column.startswith("comparable_")
        ]
        for column in uncertainty_columns:
            result.loc[mask, column] = subset[column].to_numpy()
    return result


def build_fingerprints_all_modes(
    frame: pd.DataFrame,
    window_days: Iterable[int] = (30, 90, 365),
    step_days: int = 7,
    minimum_window_events: int = 1,
    minimum_reference_windows: int = 10,
) -> pd.DataFrame:
    """Build complete and declustered fingerprints in one temporal pass.

    A shared pass avoids holding the large temporary allocations created by two
    independent multi-century builds. Each mode still receives its own
    magnitude-completeness thresholds and percentile reference population.
    """
    preferred = preferred_events(frame).copy()
    mode_events: dict[str, pd.DataFrame] = {}
    mode_thresholds: dict[
        str,
        dict[tuple[str, str], dict[str, float | int | str | None]],
    ] = {}

    for mode in ("complete", "declustered"):
        events = select_catalogue_mode(preferred, mode).copy()
        events["origin_time_utc"] = pd.to_datetime(
            events["origin_time_utc"],
            utc=True,
            errors="coerce",
        )
        events = events.dropna(
            subset=["origin_time_utc", "tectonic_domain"],
        )
        events = assign_observation_epoch(events)
        mode_events[mode] = events
        mode_thresholds[mode] = estimate_domain_epoch_thresholds(events)

    rows: list[dict[str, object]] = []
    domain_values = sorted(
        set(mode_events["complete"]["tectonic_domain"].dropna().astype(str))
        | set(mode_events["declustered"]["tectonic_domain"].dropna().astype(str))
    )

    for domain in domain_values:
        complete_domain = mode_events["complete"][
            mode_events["complete"]["tectonic_domain"].astype(str) == domain
        ].copy()
        declustered_domain = mode_events["declustered"][
            mode_events["declustered"]["tectonic_domain"].astype(str) == domain
        ].copy()
        epoch_values = sorted(
            set(complete_domain["observation_epoch"].dropna().astype(str))
            | set(declustered_domain["observation_epoch"].dropna().astype(str))
        )

        for epoch_key in epoch_values:
            groups: dict[str, pd.DataFrame] = {}
            for mode, domain_group in (
                ("complete", complete_domain),
                ("declustered", declustered_domain),
            ):
                groups[mode] = (
                    domain_group[
                        domain_group["observation_epoch"].astype(str)
                        == epoch_key
                    ]
                    .sort_values("origin_time_utc")
                    .reset_index(drop=True)
                )

            available = [group for group in groups.values() if not group.empty]
            if not available:
                continue
            first_date = min(
                group["origin_time_utc"].min().normalize()
                for group in available
            )
            last_date = max(
                group["origin_time_utc"].max().normalize()
                for group in available
            )

            mode_times = {
                mode: group["origin_time_utc"].to_numpy()
                for mode, group in groups.items()
            }

            for days in window_days:
                first_end = first_date + pd.Timedelta(days=int(days) - 1)
                if first_end > last_date:
                    continue
                window_ends = pd.date_range(
                    first_end,
                    last_date,
                    freq=f"{step_days}D",
                    tz="UTC",
                )
                window_starts = window_ends - pd.Timedelta(
                    days=int(days) - 1
                )
                exclusive_ends = window_ends + pd.Timedelta(days=1)

                positions: dict[str, tuple[np.ndarray, np.ndarray]] = {}
                for mode, times in mode_times.items():
                    positions[mode] = (
                        np.searchsorted(
                            times,
                            window_starts.to_numpy(),
                            side="left",
                        ),
                        np.searchsorted(
                            times,
                            exclusive_ends.to_numpy(),
                            side="left",
                        ),
                    )

                eligible_positions = np.flatnonzero(
                    np.logical_or.reduce(
                        [
                            (right - left) >= minimum_window_events
                            for left, right in positions.values()
                        ]
                    )
                )
                for position in eligible_positions:
                    window_start = window_starts[int(position)]
                    window_end = window_ends[int(position)]
                    for mode in ("complete", "declustered"):
                        group = groups[mode]
                        left_positions, right_positions = positions[mode]
                        left = int(left_positions[position])
                        right = int(right_positions[position])
                        if right - left < minimum_window_events:
                            continue
                        selected = group.iloc[left:right]
                        epoch = observation_epoch_for_timestamp(window_end)
                        metadata = mode_thresholds[mode].get(
                            (domain, epoch_key),
                            {
                                "epoch_key": epoch.key,
                                "epoch_label": epoch.label,
                                "estimated_mc": None,
                                "comparison_threshold": (
                                    epoch.minimum_comparable_magnitude
                                ),
                                "epoch_event_count": int(len(group)),
                            },
                        )
                        fingerprint = _window_fingerprint(
                            group,
                            selected,
                            window_start,
                            window_end,
                            int(days),
                            float(metadata["comparison_threshold"]),
                            metadata,
                        )
                        fingerprint["tectonic_domain"] = domain
                        fingerprint["catalogue_mode"] = mode
                        rows.append(fingerprint)

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result = result.sort_values(
        ["catalogue_mode", "tectonic_domain", "window_days", "window_end"]
    ).reset_index(drop=True)

    for days in sorted(set(int(value) for value in window_days)):
        mask = result["window_days"] == days
        subset = result.loc[mask].copy()
        _running_percentiles(
            subset,
            ["catalogue_mode", "tectonic_domain", "window_days"],
            "event_rate_per_30d",
            "historical",
            minimum_reference_windows,
            window_days=days,
            step_days=step_days,
        )
        _running_percentiles(
            subset,
            [
                "catalogue_mode",
                "tectonic_domain",
                "window_days",
                "comparison_epoch",
            ],
            "comparable_event_rate_per_30d",
            "comparable",
            minimum_reference_windows,
            window_days=days,
            step_days=step_days,
        )
        uncertainty_columns = [
            column
            for column in subset.columns
            if column.startswith("historical_")
            or column.startswith("comparable_")
        ]
        for column in uncertainty_columns:
            result.loc[mask, column] = subset[column].to_numpy()
    return result
