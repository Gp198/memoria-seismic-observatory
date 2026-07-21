import pandas as pd

from src.backtesting.replay import run_replay
from src.demo import generate_demo_events
from src.features.fingerprints import build_fingerprints


def test_replay_runs_without_using_post_cutoff_fingerprints():
    events = generate_demo_events()
    fingerprints = build_fingerprints(events, window_days=(90,), step_days=30)
    result = run_replay(
        events,
        fingerprints,
        cutoff="2020-01-01",
        domain="Margem Sudoeste Ibérica",
        window_days=90,
        threshold_magnitude=3.5,
        horizon_days=30,
        k=3,
        exclusion_days=180,
        diversity_days=180,
    )
    assert result.cutoff == pd.Timestamp("2020-01-01", tz="UTC")
    assert result.similarity.target["window_end"] <= result.cutoff
    assert 0 <= result.analogue_probability <= 1



def test_historical_rate_handles_millennial_catalogue():
    import pandas as pd

    from src.backtesting.replay import _historical_rate

    events = pd.DataFrame(
        {
            "tectonic_domain": ["X", "X", "X"],
            "origin_time_utc": pd.to_datetime(
                [
                    "1700-01-01T00:00:00Z",
                    "1755-11-01T09:40:00Z",
                    "2020-01-01T00:00:00Z",
                ],
                utc=True,
            ),
            "magnitude_comparable": [4.0, 8.5, 4.2],
        }
    )
    probability = _historical_rate(
        events,
        "X",
        pd.Timestamp("2026-01-01", tz="UTC"),
        4.0,
        30,
    )
    assert 0.0 <= probability <= 1.0



def test_empirical_and_poisson_share_training_exposure():
    from src.backtesting.replay import _baseline_estimate

    dates = pd.date_range(
        "2008-01-01",
        "2019-12-31",
        freq="180D",
        tz="UTC",
    )
    events = pd.DataFrame(
        {
            "tectonic_domain": ["X"] * len(dates),
            "origin_time_utc": dates,
            "magnitude_comparable": [4.2] * len(dates),
        }
    )
    estimate = _baseline_estimate(
        events,
        "X",
        pd.Timestamp("2020-01-01", tz="UTC"),
        4.0,
        30,
    )
    assert estimate.threshold_event_count == len(dates)
    assert estimate.exposure_days > 0
    assert estimate.empirical_window_count > 0
    assert estimate.poisson_lambda_per_day > 0
    assert estimate.poisson_probability > 0
    assert estimate.empirical_probability > 0
