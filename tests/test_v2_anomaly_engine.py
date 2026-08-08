import numpy as np
import pandas as pd

from src.anomalies.engine import assess_anomaly, robust_zscore


def _fingerprints(n=80, anomalous=False):
    rng=np.random.default_rng(42)
    dates=pd.date_range("2018-01-01", periods=n, freq="7D", tz="UTC")
    data=pd.DataFrame({
        "window_start":dates-pd.Timedelta(days=89),
        "window_end":dates,
        "comparison_epoch":["contemporary_network"]*n,
        "comparable_event_rate_per_30d":rng.normal(12,2,n),
        "maximum_magnitude":rng.normal(3.2,.2,n),
        "mean_magnitude":rng.normal(2.1,.1,n),
        "median_depth_km":rng.normal(12,2,n),
        "depth_std_km":rng.normal(4,.5,n),
        "spatial_dispersion_km":rng.normal(45,6,n),
        "log10_total_energy_j":rng.normal(9,.3,n),
        "data_quality_score":[.9]*n,
    })
    if anomalous:
        for c in ["comparable_event_rate_per_30d","maximum_magnitude","log10_total_energy_j"]:
            data.loc[data.index[-4:],c] = data[c].median()+6*data[c].std()
    return data


def test_robust_zscore_large_outlier():
    history=np.array([1,1.1,.9,1.05,.95,1.0,1.02])
    assert robust_zscore(3,history)>5


def test_anomaly_engine_returns_components():
    result=assess_anomaly(_fingerprints())
    assert result.method_total==5
    assert 0<=result.score<=100


def test_anomaly_engine_detects_multisignal_shift():
    result=assess_anomaly(_fingerprints(anomalous=True))
    assert result.score>40
    assert result.method_agreement>=1
