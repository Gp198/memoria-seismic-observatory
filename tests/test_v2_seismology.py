import numpy as np
import pandas as pd

from src.seismology.gutenberg_richter import estimate_b_value, rolling_b_value
from src.seismology.migration import estimate_migration


def test_b_value_estimate():
    rng=np.random.default_rng(1)
    mags=2.0+rng.exponential(.45,300)
    result=estimate_b_value(mags,2.0)
    assert result.sufficient_data
    assert result.b_value>0
    assert result.sigma is not None


def test_rolling_b_value():
    rng=np.random.default_rng(2)
    frame=pd.DataFrame({
        "origin_time_utc":pd.date_range("2020-01-01",periods=200,freq="D",tz="UTC"),
        "magnitude_comparable":2+rng.exponential(.5,200),
    })
    result=rolling_b_value(frame,2.0,window_events=80,step_events=20)
    assert not result.empty


def test_migration_detects_direction():
    n=30
    frame=pd.DataFrame({
        "origin_time_utc":pd.date_range("2024-01-01",periods=n,freq="D",tz="UTC"),
        "latitude":np.linspace(38,38.3,n),
        "longitude":np.linspace(-10,-9.5,n),
        "depth_km":np.linspace(10,15,n),
    })
    result=estimate_migration(frame)
    assert result.sufficient_data
    assert result.distance_km>10
    assert result.speed_km_per_month>0

from src.seismology.gutenberg_richter import estimate_scientific_b_value, format_b_sigma


def _scientific_events_for_b_value():
    rng = np.random.default_rng(42)
    n_ml = 160
    n_mb = 80
    dates_ml = pd.date_range("2022-01-01", periods=n_ml, freq="5D", tz="UTC")
    dates_mb = pd.date_range("2022-01-02", periods=n_mb, freq="10D", tz="UTC")
    ml = 1.5 + rng.exponential(0.45, n_ml)
    mb = 2.0 + rng.exponential(0.55, n_mb)
    return pd.DataFrame({
        "origin_time_utc": list(dates_ml) + list(dates_mb),
        "magnitude_original_value": list(ml) + list(mb),
        "magnitude_original_type": ["ML"] * n_ml + ["mb"] * n_mb,
        "magnitude_type": ["ML"] * n_ml + ["mb"] * n_mb,
        "magnitude_comparable": list(ml) + list(mb),
        "magnitude_homogenization_status": ["review_required"] * (n_ml + n_mb),
        "source": ["IPMA"] * n_ml + ["ISC"] * n_mb,
    })


def test_operational_b_value_uses_single_source_and_scale_cohort():
    events = _scientific_events_for_b_value()
    assessment, population = estimate_scientific_b_value(events, "operational", minimum_events=50)
    assert assessment.status == "scale_coherent_exploratory"
    assert assessment.magnitude_types == ("ML",)
    assert assessment.sources == ("IPMA",)
    assert population.magnitude_column == "magnitude_original_value"
    assert assessment.systematic_uncertainty_dominant
    assert assessment.estimate.sufficient_data


def test_validated_b_value_refuses_when_reviewed_coverage_is_too_small():
    events = _scientific_events_for_b_value()
    events.loc[events.index[:10], "magnitude_homogenization_status"] = "reviewed_identity"
    assessment, _ = estimate_scientific_b_value(events, "validated", minimum_events=50)
    assert assessment.status == "insufficient"
    assert not assessment.estimate.sufficient_data


def test_b_sigma_format_avoids_false_zero_precision():
    assert format_b_sigma(0.0038) == "σ estatístico <0,01"
    assert format_b_sigma(0.027).startswith("σ estatístico 0.03")
