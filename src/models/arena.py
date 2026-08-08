from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss

from src.models.etas import forecast_etas_lite


@dataclass(frozen=True)
class ModelArenaResult:
    scores: pd.DataFrame
    metrics: pd.DataFrame


def add_etas_lite_scores(
    events: pd.DataFrame,
    replay_scores: pd.DataFrame,
    domain: str,
    threshold_magnitude: float,
    horizon_days: int,
) -> pd.DataFrame:
    scores = replay_scores.copy()
    if scores.empty:
        return scores
    domain_events = events[events["tectonic_domain"] == domain].copy()
    probabilities = []
    expected = []
    for cutoff in pd.to_datetime(scores["cutoff"], utc=True):
        estimate = forecast_etas_lite(domain_events, cutoff, horizon_days, threshold_magnitude)
        probabilities.append(estimate.probability)
        expected.append(estimate.expected_events)
    scores["etas_lite_probability"] = probabilities
    scores["etas_lite_expected_events"] = expected
    observed = scores["observed_outcome"].astype(float)
    scores["brier_etas_lite"] = (scores["etas_lite_probability"] - observed) ** 2
    return scores


def summarise_arena(scores: pd.DataFrame) -> ModelArenaResult:
    if scores.empty:
        return ModelArenaResult(scores, pd.DataFrame())
    models = {
        "MEMÓRIA famílias": "analogue_probability",
        "Empírico": "historical_rate_probability",
        "Poisson": "poisson_probability",
        "ETAS-lite experimental": "etas_lite_probability",
    }
    rows = []
    y = scores["observed_outcome"].astype(int)
    poisson_brier = float(pd.to_numeric(scores.get("brier_poisson"), errors="coerce").mean())
    for name, column in models.items():
        if column not in scores:
            continue
        valid = scores[[column, "observed_outcome"]].dropna()
        if valid.empty:
            continue
        yv = valid["observed_outcome"].astype(int)
        pv = valid[column].astype(float).clip(0, 1)
        brier = float(brier_score_loss(yv, pv))
        ap = float(average_precision_score(yv, pv)) if yv.nunique() > 1 else np.nan
        bss = float(1.0 - brier/poisson_brier) if poisson_brier > 0 else np.nan
        rows.append({
            "Modelo": name,
            "Cortes": int(len(valid)),
            "Eventos observados": int(yv.sum()),
            "Probabilidade média": float(pv.mean()),
            "Brier": brier,
            "BSS vs Poisson": bss,
            "Average Precision": ap,
        })
    return ModelArenaResult(scores=scores, metrics=pd.DataFrame(rows))


def summarise_global_leaderboard(metrics_grid: pd.DataFrame) -> pd.DataFrame:
    """Aggregate a magnitude × horizon arena without hiding scenario heterogeneity.

    The leaderboard treats every threshold/horizon scenario as one experimental
    unit.  It therefore reports scenario-level means/medians and average rank,
    rather than pooling raw Brier values across event-prevalence regimes.
    """
    if metrics_grid is None or metrics_grid.empty:
        return pd.DataFrame()

    required = {"Modelo", "Brier", "BSS vs Poisson", "Average Precision"}
    if not required.issubset(metrics_grid.columns):
        return pd.DataFrame()

    frame = metrics_grid.copy()
    scenario_columns = [
        column
        for column in ("Magnitude-alvo", "Horizonte", "Fingerprint")
        if column in frame.columns
    ]
    if not scenario_columns:
        frame["_scenario"] = np.arange(len(frame))
        scenario_columns = ["_scenario"]

    frame["Brier"] = pd.to_numeric(frame["Brier"], errors="coerce")
    frame["BSS vs Poisson"] = pd.to_numeric(frame["BSS vs Poisson"], errors="coerce")
    frame["Average Precision"] = pd.to_numeric(frame["Average Precision"], errors="coerce")
    frame["Cortes"] = pd.to_numeric(frame.get("Cortes"), errors="coerce")
    frame["Eventos observados"] = pd.to_numeric(frame.get("Eventos observados"), errors="coerce")

    frame["Rank Brier"] = frame.groupby(scenario_columns, dropna=False)["Brier"].rank(
        method="min", ascending=True
    )
    min_brier = frame.groupby(scenario_columns, dropna=False)["Brier"].transform("min")
    frame["Vitória Brier"] = np.isclose(frame["Brier"], min_brier, rtol=1e-12, atol=1e-12)
    frame["Skill positivo"] = frame["BSS vs Poisson"] > 0

    rows: list[dict[str, object]] = []
    for model, group in frame.groupby("Modelo", dropna=False):
        valid_brier = group["Brier"].dropna()
        valid_bss = group["BSS vs Poisson"].dropna()
        valid_ap = group["Average Precision"].dropna()
        valid_rank = group["Rank Brier"].dropna()
        rows.append(
            {
                "Modelo": model,
                "Cenários": int(len(group)),
                "Cortes somados": int(group["Cortes"].fillna(0).sum()),
                "Eventos observados somados": int(group["Eventos observados"].fillna(0).sum()),
                "Brier médio por cenário": float(valid_brier.mean()) if not valid_brier.empty else np.nan,
                "BSS médio vs Poisson": float(valid_bss.mean()) if not valid_bss.empty else np.nan,
                "BSS mediano vs Poisson": float(valid_bss.median()) if not valid_bss.empty else np.nan,
                "Average Precision média": float(valid_ap.mean()) if not valid_ap.empty else np.nan,
                "Vitórias Brier": int(group["Vitória Brier"].fillna(False).sum()),
                "Rank Brier médio": float(valid_rank.mean()) if not valid_rank.empty else np.nan,
                "Cenários com skill > Poisson": int(group["Skill positivo"].fillna(False).sum()),
                "Taxa de skill > Poisson": float(group["Skill positivo"].mean()) if len(group) else np.nan,
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        ["Rank Brier médio", "BSS médio vs Poisson", "Average Precision média"],
        ascending=[True, False, False],
        na_position="last",
    ).reset_index(drop=True)
