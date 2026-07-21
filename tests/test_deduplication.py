import pandas as pd

from src.quality.deduplication import deduplicate_events
from src.schema import ensure_event_schema


def test_duplicate_group_and_preferred_record():
    frame = ensure_event_schema(
        pd.DataFrame(
            [
                {
                    "event_id_memoria": "a",
                    "source_event_id": "1",
                    "source": "IPMA",
                    "origin_time_utc": "2026-01-01T00:00:00Z",
                    "latitude": 38.0,
                    "longitude": -9.0,
                    "magnitude_value": 3.0,
                    "quality_score": 0.9,
                    "record_status": "preliminary",
                    "is_preferred_record": True,
                },
                {
                    "event_id_memoria": "b",
                    "source_event_id": "2",
                    "source": "ISC",
                    "origin_time_utc": "2026-01-01T00:00:20Z",
                    "latitude": 38.02,
                    "longitude": -9.01,
                    "magnitude_value": 3.1,
                    "quality_score": 0.8,
                    "record_status": "reviewed",
                    "is_preferred_record": True,
                },
            ]
        )
    )
    result = deduplicate_events(frame)
    assert result["duplicate_group_id"].notna().all()
    assert result["is_preferred_record"].sum() == 1
