import numpy as np

from src.quality.completeness import estimate_magnitude_completeness


def test_completeness_requires_sample():
    estimate = estimate_magnitude_completeness([1.0, 2.0, 3.0], minimum_events=10)
    assert estimate.mc is None
    assert not estimate.sufficient_data


def test_completeness_estimates_peak_bin():
    rng = np.random.default_rng(42)
    values = np.concatenate([rng.normal(2.0, 0.08, 100), rng.normal(2.8, 0.2, 30)])
    estimate = estimate_magnitude_completeness(values, minimum_events=50)
    assert estimate.sufficient_data
    assert 1.8 <= estimate.mc <= 2.2
