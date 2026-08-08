import numpy as np
import pandas as pd

from src.regimes.states import infer_regimes
from src.models.etas import forecast_etas_lite


def test_regime_engine():
    rng=np.random.default_rng(3); n=100
    dates=pd.date_range("2020-01-01",periods=n,freq="7D",tz="UTC")
    half=n//2
    frame=pd.DataFrame({
        "window_start":dates-pd.Timedelta(days=89),"window_end":dates,
        "comparable_event_rate_per_30d":np.r_[rng.normal(5,1,half),rng.normal(20,2,n-half)],
        "maximum_magnitude":np.r_[rng.normal(3,.2,half),rng.normal(4,.2,n-half)],
        "median_depth_km":rng.normal(12,1,n),
        "spatial_dispersion_km":np.r_[rng.normal(60,5,half),rng.normal(25,4,n-half)],
        "log10_total_energy_j":np.r_[rng.normal(8,.2,half),rng.normal(10,.2,n-half)],
    })
    result=infer_regimes(frame)
    assert result.cluster_count>=2
    assert result.current_regime is not None
    assert not result.transition_matrix.empty


def test_etas_lite_probability_is_bounded():
    events=pd.DataFrame({
        "origin_time_utc":pd.date_range("2020-01-01",periods=60,freq="30D",tz="UTC"),
        "magnitude_comparable":[4.1]*60,
    })
    estimate=forecast_etas_lite(events,pd.Timestamp("2025-01-01",tz="UTC"),30,4.0)
    assert 0<=estimate.probability<=1
    assert estimate.expected_events>=0


def test_etas_lite_supports_catalogues_longer_than_pandas_timedelta_range():
    events = pd.DataFrame({
        "origin_time_utc": pd.to_datetime([
            "1719-01-01T00:00:00Z",
            "1720-01-01T00:00:00Z",
            "2025-12-01T00:00:00Z",
            "2025-12-15T00:00:00Z",
        ], utc=True),
        "magnitude_comparable": [4.1, 4.2, 4.0, 4.3],
    })
    estimate = forecast_etas_lite(
        events,
        pd.Timestamp("2026-01-01", tz="UTC"),
        30,
        4.0,
    )
    assert 0 <= estimate.probability <= 1
    assert estimate.parameters.training_events == 4
    assert estimate.expected_events >= 0
