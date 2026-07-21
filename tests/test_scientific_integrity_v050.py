import pandas as pd

from src.backtesting.validation import summarise_backtest
from src.quality.declustering import annotate_declustering, declustering_summary
from src.quality.magnitude import select_magnitude_policy, magnitude_policy_summary


def _events():
    return pd.DataFrame({
        "event_id_memoria":["a","b","c","d"],
        "source_event_id":["a","b","c","d"],
        "source":["X"]*4,
        "origin_time_utc":pd.to_datetime(["2020-01-01","2020-01-02",None,"2020-02-01"],utc=True),
        "latitude":[38.0,38.01,38.0,39.0],
        "longitude":[-9.0,-9.01,-9.0,-10.0],
        "magnitude_value":[4.0,2.0,3.0,3.5],
        "magnitude_type":["MW","ML","MW","ML"],
        "magnitude_original_value":[4.0,2.0,3.0,3.5],
        "magnitude_original_type":["MW","ML","MW","ML"],
        "magnitude_comparable":[4.0,2.0,3.0,3.5],
        "magnitude_homogenization_status":["reviewed_identity","review_required","reviewed_identity","review_required"],
        "is_preferred_record":[True]*4,
    })


def test_declustering_reconciliation_closes():
    annotated=annotate_declustering(_events())
    summary=declustering_summary(annotated)
    assert summary["reconciliation_gap"] == 0
    assert summary["ineligible_events"] == 1
    assert summary["background_events"] + summary["associated_events"] + summary["ineligible_events"] == summary["preferred_events"]


def test_validated_magnitude_policy_filters_fallbacks():
    events=_events()
    summary=magnitude_policy_summary(events)
    validated=select_magnitude_policy(events,"validated")
    assert summary["validated_events"] == 2
    assert len(validated) == 2


def test_rare_event_thresholds_and_calibration_status():
    scores=pd.DataFrame({
        "cutoff":pd.date_range("2000-01-01",periods=40,freq="90D",tz="UTC"),
        "analogue_probability":[0.01]*38+[0.04,0.06],
        "historical_rate_probability":[0.02]*40,
        "poisson_probability":[0.018]*40,
        "observed_outcome":[False]*38+[True,True],
        "brier_analogue":[0.0001]*38+[0.9216,0.8836],
        "brier_historical":[0.0004]*38+[0.9604,0.9604],
        "brier_poisson":[0.000324]*38+[0.964324,0.964324],
    })
    result=summarise_backtest(scores)
    assert set(result.classification["Limiar de decisão"].unique()) == {0.005,0.01,0.02,0.05,0.10}
    assert result.calibration_status in {"unavailable","experimental","adequate"}
    assert not result.precision_recall.empty
    assert {"IC 95% inferior","IC 95% superior","Eventos observados"}.issubset(result.calibration.columns)
