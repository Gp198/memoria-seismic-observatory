import pandas as pd

from src.schema import ensure_event_schema


def test_historical_sentinel_values_become_null():
    frame = ensure_event_schema(
        pd.DataFrame(
            [
                {
                    "event_id_memoria": "x",
                    "source_event_id": "1",
                    "source": "AHEAD",
                    "origin_time_utc": "1755-11-01T09:40:00Z",
                    "latitude": 36.0,
                    "longitude": -10.0,
                    "depth_km": -99,
                    "magnitude_value": -99,
                    "magnitude_comparable": -99,
                    "is_preferred_record": True,
                }
            ]
        )
    )
    assert pd.isna(frame.iloc[0]["magnitude_value"])
    assert pd.isna(frame.iloc[0]["magnitude_comparable"])
    assert pd.isna(frame.iloc[0]["depth_km"])
