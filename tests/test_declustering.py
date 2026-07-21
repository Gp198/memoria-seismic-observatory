import pandas as pd

from src.quality.declustering import annotate_declustering, select_catalogue_mode


def test_pilot_declustering_marks_close_later_event_as_associated():
    frame = pd.DataFrame(
        {
            "event_id_memoria": ["main", "after", "far"],
            "source_event_id": ["1", "2", "3"],
            "source": ["ISC", "ISC", "ISC"],
            "origin_time_utc": pd.to_datetime(
                [
                    "2020-01-01T00:00:00Z",
                    "2020-01-02T00:00:00Z",
                    "2020-01-02T00:00:00Z",
                ],
                utc=True,
            ),
            "latitude": [38.0, 38.02, 41.0],
            "longitude": [-9.0, -9.02, -9.0],
            "magnitude_value": [5.0, 2.5, 2.5],
            "magnitude_comparable": [5.0, 2.5, 2.5],
            "is_preferred_record": [True, True, True],
        }
    )
    result = annotate_declustering(frame)
    roles = result.set_index("event_id_memoria")["cluster_role"].astype(str)
    assert roles["main"] == "mainshock"
    assert roles["after"] == "associated_event"
    assert roles["far"] == "background"
    declustered = select_catalogue_mode(result, "declustered")
    assert set(declustered["event_id_memoria"].astype(str)) == {"main", "far"}
