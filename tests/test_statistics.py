import numpy as np

from src.quality.statistics import (
    effective_sample_size,
    percentile_uncertainty,
    wilson_interval,
)


def test_effective_sample_size_accounts_for_overlapping_windows():
    values = np.linspace(0.0, 1.0, 567)
    effective, overlap_factor, _ = effective_sample_size(
        values,
        window_days=90,
        step_days=7,
    )
    assert overlap_factor == 13
    assert effective <= 567 / 13 + 1e-9
    assert effective >= 1


def test_percentile_uncertainty_returns_bounded_interval():
    result = percentile_uncertainty(
        np.arange(100, dtype=float),
        target_value=30.0,
        window_days=90,
        step_days=7,
        minimum_reference_windows=10,
    )
    assert result.percentile is not None
    assert result.ci_lower is not None
    assert result.ci_upper is not None
    assert 0 <= result.ci_lower <= result.percentile <= result.ci_upper <= 1


def test_wilson_interval_handles_effective_non_integer_sample():
    lower, upper = wilson_interval(0.31, 43.6)
    assert lower is not None and upper is not None
    assert 0 <= lower < 0.31 < upper <= 1


def test_moving_block_bootstrap_returns_bounded_interval():
    from src.quality.statistics import moving_block_percentile_interval

    result = moving_block_percentile_interval(
        np.sin(np.linspace(0, 20, 200)),
        target_value=0.2,
        block_length=10,
        resamples=200,
        random_seed=7,
    )
    assert result.percentile is not None
    assert result.ci_lower is not None
    assert result.ci_upper is not None
    assert 0 <= result.ci_lower <= result.ci_upper <= 1
    assert result.block_length == 10
