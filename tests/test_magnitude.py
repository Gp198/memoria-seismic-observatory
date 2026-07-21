import pandas as pd

from src.quality.magnitude import homogenize_magnitudes


def test_moment_magnitude_is_reviewed_identity():
    frame = pd.DataFrame(
        {
            "event_id_memoria": ["a"],
            "source_event_id": ["1"],
            "source": ["ISC"],
            "origin_time_utc": ["2020-01-01T00:00:00Z"],
            "magnitude_value": [4.2],
            "magnitude_type": ["Mw"],
            "is_preferred_record": [True],
        }
    )
    result = homogenize_magnitudes(frame)
    assert result.iloc[0]["magnitude_comparable"] == 4.2
    assert (
        result.iloc[0]["magnitude_homogenization_status"]
        == "reviewed_identity"
    )
    assert result.iloc[0]["magnitude_original_type"] == "Mw"


def test_unknown_scale_is_retained_but_flagged():
    frame = pd.DataFrame(
        {
            "event_id_memoria": ["a"],
            "source_event_id": ["1"],
            "source": ["ISC"],
            "origin_time_utc": ["2020-01-01T00:00:00Z"],
            "magnitude_value": [3.1],
            "magnitude_type": [pd.NA],
            "is_preferred_record": [True],
        }
    )
    result = homogenize_magnitudes(frame)
    assert result.iloc[0]["magnitude_comparable"] == 3.1
    assert result.iloc[0]["magnitude_homogenization_status"] == "unknown_scale"
    assert result.iloc[0]["magnitude_conversion_uncertainty"] >= 0.5
