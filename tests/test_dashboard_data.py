import pandas as pd

from src.reporting.dashboard_data import (
    build_event_map_figure,
    prepare_dashboard_events,
    prepare_dashboard_fingerprints,
    prepare_map_data,
)


def test_prepare_map_data_handles_datetime_and_nullable_floats():
    frame = pd.DataFrame(
        {
            "origin_time_utc": pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"], utc=True
            ),
            "latitude": pd.Series([38.0, 36.5], dtype="Float64"),
            "longitude": pd.Series([-9.0, -10.0], dtype="Float64"),
            "depth_km": pd.Series([12.0, pd.NA], dtype="Float64"),
            "magnitude_comparable": pd.Series([3.1, 4.0], dtype="Float64"),
            "location_text": pd.Series(["Lisboa", pd.NA], dtype="string"),
        }
    )
    result = prepare_map_data(frame, 1.5)
    assert len(result) == 2
    assert str(result["latitude"].dtype) == "float64"
    assert "2026-01-01" in result.iloc[0]["hover_text"]


def test_event_map_figure_builds_without_dtype_promotion_error():
    frame = pd.DataFrame(
        {
            "origin_time_utc": ["2026-01-01T00:00:00Z"],
            "latitude": pd.Series([38.0], dtype="Float64"),
            "longitude": pd.Series([-9.0], dtype="Float64"),
            "depth_km": pd.Series([10.0], dtype="Float64"),
            "magnitude_comparable": pd.Series([3.2], dtype="Float64"),
            "location_text": pd.Series(["Teste"], dtype="string"),
        }
    )
    figure = build_event_map_figure(frame, 1.0)
    assert len(figure.data) == 1
    assert figure.data[0].type == "scattermap"


def test_dashboard_type_normalisation():
    events = prepare_dashboard_events(
        pd.DataFrame(
            {
                "origin_time_utc": ["2026-01-01"],
                "latitude": pd.Series([38.0], dtype="Float64"),
                "longitude": pd.Series([-9.0], dtype="Float64"),
                "magnitude_comparable": pd.Series([3.0], dtype="Float64"),
            }
        )
    )
    assert str(events["latitude"].dtype) == "float64"

    fingerprints = prepare_dashboard_fingerprints(
        pd.DataFrame(
            {
                "window_end": ["2026-01-01"],
                "event_count": pd.Series([10], dtype="Int64"),
            }
        )
    )
    assert str(fingerprints["event_count"].dtype) == "float64"



def test_calendar_span_handles_more_than_a_millennium():
    import pandas as pd

    from src.reporting.dashboard_data import (
        build_temporal_aggregation,
        calendar_span_years,
        safe_fractional_date,
    )

    import numpy as np

    dates = pd.Series(
        [
            np.datetime64("1000-01-01T00:00:00", "us"),
            np.datetime64("1755-11-01T09:40:00", "us"),
            np.datetime64("2026-07-20T00:00:00", "us"),
        ],
        dtype="datetime64[us]",
    )
    assert calendar_span_years(dates) == 1026

    frame = pd.DataFrame(
        {
            "origin_time_utc": dates,
            "latitude": [38.0, 36.0, 37.0],
            "longitude": [-9.0, -10.0, -8.0],
            "magnitude_comparable": [4.0, 8.5, 3.0],
        }
    )
    result = build_temporal_aggregation(frame)
    assert result.x_column == "year"
    assert result.data["events"].sum() == 3
    assert safe_fractional_date(dates, 0.5).year == 1755



def test_catalogue_consolidation_summary():
    from src.reporting.dashboard_data import (
        catalogue_consolidation_summary,
    )

    frame = pd.DataFrame(
        {
            "is_preferred_record": [True, False, True, False],
            "duplicate_group_id": ["A", "A", pd.NA, "B"],
        }
    )
    result = catalogue_consolidation_summary(frame)
    assert result["raw_records"] == 4
    assert result["consolidated_events"] == 2
    assert result["redundant_records"] == 2
    assert result["duplicate_groups"] == 2
    assert result["consolidation_rate"] == 0.5


def test_map_modes_build_supported_plotly_traces():
    import pandas as pd

    from src.reporting.dashboard_data import build_event_map_figure

    frame = pd.DataFrame(
        {
            "origin_time_utc": pd.to_datetime(
                ["2020-01-01", "2020-01-02"], utc=True
            ),
            "latitude": [38.0, 37.5],
            "longitude": [-9.0, -10.0],
            "magnitude_comparable": [2.0, 3.0],
            "depth_km": [10.0, 20.0],
            "location_text": ["A", "B"],
            "source": ["ISC", "IPMA"],
        }
    )
    cluster = build_event_map_figure(frame, 1.0, display_mode="cluster")
    density = build_event_map_figure(frame, 1.0, display_mode="density")
    points = build_event_map_figure(frame, 1.0, display_mode="points")
    assert cluster.data[0].type == "scattermap"
    assert density.data[0].type == "densitymap"
    assert points.data[0].type == "scattermap"


def test_activity_assessment_uses_confidence_interval():
    from src.reporting.dashboard_data import assess_activity_state

    normal = assess_activity_state(0.32, 0.11, 0.63, 9.4)
    assert normal.level == "normal"
    assert not normal.robust_elevation

    inconclusive = assess_activity_state(0.78, 0.65, 0.91, 20)
    assert inconclusive.inconclusive

    elevated = assess_activity_state(0.92, 0.84, 0.98, 20)
    assert elevated.robust_elevation
