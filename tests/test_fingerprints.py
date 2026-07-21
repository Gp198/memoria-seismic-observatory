from src.demo import generate_demo_events
from src.features.fingerprints import build_fingerprints


def test_fingerprints_are_generated():
    events = generate_demo_events()
    fingerprints = build_fingerprints(events, window_days=(90,), step_days=30)
    assert not fingerprints.empty
    assert {"event_count", "maximum_magnitude", "spatial_dispersion_km"}.issubset(
        fingerprints.columns
    )



def test_comparable_percentile_is_epoch_specific():
    events = generate_demo_events()
    fingerprints = build_fingerprints(
        events,
        window_days=(90,),
        step_days=30,
        minimum_reference_windows=3,
    )
    assert {
        "comparison_epoch",
        "comparison_magnitude_threshold",
        "comparable_event_count",
        "comparable_event_rate_per_30d",
        "comparable_percentile_event_rate",
        "source_share_isc",
        "depth_coverage_ratio",
    }.issubset(fingerprints.columns)


def test_percentile_reports_effective_sample_size_and_interval():
    events = generate_demo_events()
    fingerprints = build_fingerprints(
        events,
        window_days=(90,),
        step_days=7,
        minimum_reference_windows=3,
    )
    latest = fingerprints.sort_values("window_end").iloc[-1]
    assert latest["comparable_reference_windows"] >= 3
    assert latest["comparable_effective_sample_size"] <= latest[
        "comparable_reference_windows"
    ]
    assert 0 <= latest["comparable_percentile_ci_lower"] <= 1
    assert 0 <= latest["comparable_percentile_ci_upper"] <= 1
