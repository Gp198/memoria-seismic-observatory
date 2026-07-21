import pandas as pd

from src.quality.epochs import (
    estimate_domain_epoch_thresholds,
    observation_epoch_for_year,
)


def test_epoch_boundaries():
    assert observation_epoch_for_year(1755).key == "historical_pre_instrumental"
    assert observation_epoch_for_year(1950).key == "early_instrumental"
    assert observation_epoch_for_year(1980).key == "modern_network"
    assert observation_epoch_for_year(2026).key == "contemporary_network"


def test_epoch_threshold_respects_policy_floor():
    frame = pd.DataFrame(
        {
            "origin_time_utc": pd.to_datetime(
                ["1755-01-01", "1756-01-01", "1757-01-01"],
                utc=True,
            ),
            "tectonic_domain": ["X", "X", "X"],
            "magnitude_comparable": [3.0, 3.5, 4.0],
        }
    )
    result = estimate_domain_epoch_thresholds(frame, minimum_events=20)
    assert (
        result[("X", "historical_pre_instrumental")][
            "comparison_threshold"
        ]
        == 5.0
    )
