import numpy as np
import pandas as pd

from src.backtesting.validation import (
    add_expanding_isotonic_calibration,
    brier_skill_score,
    summarise_backtest,
)


def _scores(count: int = 80) -> pd.DataFrame:
    probabilities = np.linspace(0.05, 0.95, count)
    outcomes = probabilities > 0.55
    empirical = np.full(count, outcomes.mean())
    poisson = np.full(count, min(0.95, outcomes.mean() + 0.05))
    return pd.DataFrame(
        {
            "cutoff": pd.date_range("2008-01-01", periods=count, freq="30D", tz="UTC"),
            "analogue_probability": probabilities,
            "historical_rate_probability": empirical,
            "poisson_probability": poisson,
            "observed_outcome": outcomes,
            "brier_analogue": (probabilities - outcomes.astype(float)) ** 2,
            "brier_historical": (empirical - outcomes.astype(float)) ** 2,
            "brier_poisson": (poisson - outcomes.astype(float)) ** 2,
        }
    )


def test_expanding_calibration_uses_only_later_rows_after_history():
    result = add_expanding_isotonic_calibration(
        _scores(),
        minimum_history=20,
    )
    assert result.loc[:19, "analogue_calibrated_probability"].isna().all()
    assert result.loc[20:, "analogue_calibrated_probability"].notna().any()


def test_backtest_summary_includes_skill_and_calibration():
    summary = summarise_backtest(
        _scores(),
        minimum_calibration_history=20,
    )
    assert summary.sample_count == 80
    assert summary.calibrated_count > 0
    assert not summary.metrics.empty
    assert not summary.calibration.empty
    assert not summary.classification.empty


def test_brier_skill_score_direction():
    assert brier_skill_score(0.1, 0.2) == 0.5
    assert brier_skill_score(0.3, 0.2) < 0


def test_backtest_grid_summary_keeps_magnitude_and_horizon():
    from src.backtesting.validation import summarise_backtest_grid

    first = _scores(40)
    first["threshold_magnitude"] = 4.0
    first["horizon_days"] = 30
    first["catalogue_mode"] = "complete"
    second = _scores(40)
    second["threshold_magnitude"] = 4.5
    second["horizon_days"] = 90
    second["catalogue_mode"] = "complete"
    summary = summarise_backtest_grid(
        pd.concat([first, second], ignore_index=True),
        minimum_calibration_history=10,
    )
    assert set(summary["threshold_magnitude"]) == {4.0, 4.5}
    assert set(summary["horizon_days"]) == {30, 90}
    assert "Erro de calibração esperado" in summary.columns
