from src.demo import generate_demo_events
from src.features.fingerprints import build_fingerprints
from src.similarity.nearest_states import nearest_states


def test_nearest_states_excludes_recent_history():
    events = generate_demo_events()
    fingerprints = build_fingerprints(events, window_days=(90,), step_days=30)
    result = nearest_states(
        fingerprints,
        "Margem Sudoeste Ibérica",
        90,
        k=3,
        exclusion_days=180,
    )
    target_end = result.target["window_end"]
    assert (result.neighbours["window_end"] <= target_end - __import__("pandas").Timedelta(days=180)).all()
    assert len(result.neighbours) == 3



def test_nearest_states_ignores_all_missing_features():
    import numpy as np
    import pandas as pd

    rows = []
    for index in range(20):
        rows.append(
            {
                "tectonic_domain": "Margem Sudoeste Ibérica",
                "window_days": 90,
                "window_start": pd.Timestamp("2000-01-01", tz="UTC")
                + pd.Timedelta(days=index * 100),
                "window_end": pd.Timestamp("2000-03-30", tz="UTC")
                + pd.Timedelta(days=index * 100),
                "event_count": 2 + index,
                "event_rate_per_30d": 1 + index / 3,
                "comparable_event_count": 2 + index,
                "comparable_event_rate_per_30d": 1 + index / 3,
                "maximum_magnitude": 2.0 + index / 20,
                "mean_magnitude": 1.5 + index / 30,
                "median_depth_km": 10 + index,
                "depth_std_km": 1 + index / 10,
                "spatial_dispersion_km": 5 + index,
                "log10_total_energy_j": 8 + index / 10,
                "days_since_previous_m3": np.nan,
                "catalogue_completeness_mc": np.nan,
                "data_quality_score": 0.8,
                "historical_percentile_event_rate": index / 20,
            }
        )
    fingerprints = pd.DataFrame(rows)
    result = nearest_states(
        fingerprints,
        "Margem Sudoeste Ibérica",
        90,
        k=3,
        exclusion_days=100,
    )
    assert len(result.neighbours) == 3
    assert "days_since_previous_m3" not in result.features
    assert "catalogue_completeness_mc" not in result.features
    assert result.feature_differences["feature"].nunique() == len(result.features)



def test_nearest_states_returns_diverse_episodes():
    import pandas as pd

    events = generate_demo_events()
    fingerprints = build_fingerprints(
        events,
        window_days=(90,),
        step_days=14,
    )
    result = nearest_states(
        fingerprints,
        "Margem Sudoeste Ibérica",
        90,
        k=5,
        exclusion_days=180,
        diversity_days=180,
    )
    dates = list(result.neighbours["window_end"])
    for index, left in enumerate(dates):
        for right in dates[index + 1:]:
            assert abs((left - right).days) >= 180


def test_feature_contributions_sum_to_one_hundred():
    events = generate_demo_events()
    fingerprints = build_fingerprints(
        events,
        window_days=(90,),
        step_days=30,
    )
    result = nearest_states(
        fingerprints,
        "Margem Sudoeste Ibérica",
        90,
        k=3,
        exclusion_days=180,
        diversity_days=180,
    )
    totals = result.feature_differences.groupby(
        "episode_id"
    )["contribution_pct"].sum()
    assert all(abs(total - 100.0) < 1e-6 for total in totals)
    assert result.neighbours["comparability_score"].between(
        0.5,
        1.0,
    ).all()



def test_temporal_families_have_separate_centres():
    events = generate_demo_events()
    fingerprints = build_fingerprints(
        events,
        window_days=(90,),
        step_days=14,
        minimum_reference_windows=3,
    )
    result = nearest_states(
        fingerprints,
        "Margem Sudoeste Ibérica",
        90,
        k=4,
        exclusion_days=180,
        family_gap_days=365,
    )
    dates = list(result.neighbours["window_end"])
    for index, left in enumerate(dates):
        for right in dates[index + 1:]:
            assert abs((left - right).days) > 365
    assert result.neighbours["family_id"].nunique() == len(
        result.neighbours
    )


def test_temporal_family_intervals_are_non_overlapping():
    import pandas as pd

    events = generate_demo_events()
    fingerprints = build_fingerprints(
        events,
        window_days=(90,),
        step_days=14,
        minimum_reference_windows=3,
    )
    result = nearest_states(
        fingerprints,
        "Margem Sudoeste Ibérica",
        90,
        k=4,
        exclusion_days=180,
        family_gap_days=365,
        family_buffer_days=90,
    )
    ordered = result.neighbours.sort_values("family_start")
    previous_end = None
    for _, row in ordered.iterrows():
        start = pd.to_datetime(row["family_start"], utc=True)
        end = pd.to_datetime(row["family_end"], utc=True)
        if previous_end is not None:
            assert start > previous_end + pd.Timedelta(days=90)
        previous_end = end


def test_adaptive_temporal_families_are_non_overlapping():
    import pandas as pd

    events = generate_demo_events()
    fingerprints = build_fingerprints(
        events,
        window_days=(90,),
        step_days=30,
        minimum_reference_windows=3,
    )
    result = nearest_states(
        fingerprints,
        "Margem Sudoeste Ibérica",
        90,
        k=4,
        exclusion_days=180,
        family_gap_days=720,
        family_buffer_days=90,
        family_method="adaptive",
    )
    assert result.family_method == "adaptive"
    ordered = result.neighbours.sort_values("family_start")
    previous_end = None
    for _, row in ordered.iterrows():
        start = pd.to_datetime(row["family_start"], utc=True)
        end = pd.to_datetime(row["family_end"], utc=True)
        if previous_end is not None:
            assert start > previous_end + pd.Timedelta(days=90)
        previous_end = end
