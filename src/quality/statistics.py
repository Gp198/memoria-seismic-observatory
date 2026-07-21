from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt
from statistics import NormalDist

import numpy as np


@dataclass(frozen=True)
class PercentileUncertainty:
    percentile: float | None
    reference_windows: int
    effective_sample_size: float
    ci_lower: float | None
    ci_upper: float | None
    overlap_factor: int
    lag1_autocorrelation: float | None


def lag1_autocorrelation(values: np.ndarray) -> float | None:
    clean = np.asarray(values, dtype=float)
    clean = clean[np.isfinite(clean)]
    if len(clean) < 3:
        return None
    left = clean[:-1]
    right = clean[1:]
    if np.isclose(np.std(left), 0.0) or np.isclose(np.std(right), 0.0):
        return None
    value = float(np.corrcoef(left, right)[0, 1])
    if not np.isfinite(value):
        return None
    return float(np.clip(value, -0.99, 0.99))


def effective_sample_size(
    values: np.ndarray,
    window_days: int,
    step_days: int,
) -> tuple[float, int, float | None]:
    clean = np.asarray(values, dtype=float)
    clean = clean[np.isfinite(clean)]
    n = len(clean)
    if n == 0:
        return 0.0, 1, None

    overlap_factor = max(1, int(ceil(window_days / max(step_days, 1))))
    non_overlapping_bound = max(1.0, n / overlap_factor)

    rho1 = lag1_autocorrelation(clean)
    if rho1 is None or rho1 <= 0:
        autocorrelation_bound = float(n)
    else:
        autocorrelation_bound = n * (1.0 - rho1) / (1.0 + rho1)

    effective = float(
        np.clip(
            min(float(n), non_overlapping_bound, autocorrelation_bound),
            1.0,
            float(n),
        )
    )
    return effective, overlap_factor, rho1


def wilson_interval(
    proportion: float,
    effective_n: float,
    confidence: float = 0.95,
) -> tuple[float | None, float | None]:
    if not np.isfinite(proportion) or effective_n <= 0:
        return None, None
    p = float(np.clip(proportion, 0.0, 1.0))
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    denominator = 1.0 + (z * z) / effective_n
    centre = (p + (z * z) / (2.0 * effective_n)) / denominator
    margin = (
        z
        * sqrt(
            (p * (1.0 - p) / effective_n)
            + ((z * z) / (4.0 * effective_n * effective_n))
        )
        / denominator
    )
    return (
        float(np.clip(centre - margin, 0.0, 1.0)),
        float(np.clip(centre + margin, 0.0, 1.0)),
    )


def percentile_uncertainty(
    prior_values: np.ndarray,
    target_value: float,
    window_days: int,
    step_days: int,
    minimum_reference_windows: int,
) -> PercentileUncertainty:
    clean = np.asarray(prior_values, dtype=float)
    clean = clean[np.isfinite(clean)]
    n = len(clean)
    effective, overlap_factor, rho1 = effective_sample_size(
        clean,
        window_days=window_days,
        step_days=step_days,
    )

    if n < minimum_reference_windows or not np.isfinite(target_value):
        return PercentileUncertainty(
            percentile=None,
            reference_windows=n,
            effective_sample_size=effective,
            ci_lower=None,
            ci_upper=None,
            overlap_factor=overlap_factor,
            lag1_autocorrelation=rho1,
        )

    percentile = float(np.mean(clean <= float(target_value)))
    lower, upper = wilson_interval(percentile, effective)
    return PercentileUncertainty(
        percentile=percentile,
        reference_windows=n,
        effective_sample_size=effective,
        ci_lower=lower,
        ci_upper=upper,
        overlap_factor=overlap_factor,
        lag1_autocorrelation=rho1,
    )


@dataclass(frozen=True)
class BootstrapPercentileInterval:
    percentile: float | None
    ci_lower: float | None
    ci_upper: float | None
    block_length: int
    resamples: int


def moving_block_percentile_interval(
    prior_values: np.ndarray,
    target_value: float,
    block_length: int | None = None,
    resamples: int = 800,
    confidence: float = 0.95,
    random_seed: int = 42,
) -> BootstrapPercentileInterval:
    """Moving-block bootstrap interval for a percentile position.

    Contiguous blocks preserve short-range temporal dependence between moving
    windows. This is a sensitivity estimate, not a replacement for a complete
    point-process uncertainty model.
    """
    values = np.asarray(prior_values, dtype=float)
    values = values[np.isfinite(values)]
    n = len(values)
    if n < 3 or not np.isfinite(target_value) or resamples < 20:
        return BootstrapPercentileInterval(
            percentile=None,
            ci_lower=None,
            ci_upper=None,
            block_length=max(1, int(block_length or 1)),
            resamples=int(resamples),
        )

    resolved_block = int(
        np.clip(
            block_length if block_length is not None else round(n ** (1.0 / 3.0)),
            2,
            n,
        )
    )
    point = float(np.mean(values <= float(target_value)))
    rng = np.random.default_rng(random_seed)
    maximum_start = max(1, n - resolved_block + 1)
    bootstrap_percentiles = np.empty(int(resamples), dtype=float)

    for index in range(int(resamples)):
        sampled_parts: list[np.ndarray] = []
        sampled_count = 0
        while sampled_count < n:
            start = int(rng.integers(0, maximum_start))
            block = values[start : start + resolved_block]
            sampled_parts.append(block)
            sampled_count += len(block)
        sample = np.concatenate(sampled_parts)[:n]
        bootstrap_percentiles[index] = float(
            np.mean(sample <= float(target_value))
        )

    alpha = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(
        bootstrap_percentiles,
        [alpha, 1.0 - alpha],
    )
    return BootstrapPercentileInterval(
        percentile=point,
        ci_lower=float(np.clip(lower, 0.0, 1.0)),
        ci_upper=float(np.clip(upper, 0.0, 1.0)),
        block_length=resolved_block,
        resamples=int(resamples),
    )
