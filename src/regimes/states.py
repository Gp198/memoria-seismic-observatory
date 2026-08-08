from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import RobustScaler


REGIME_FEATURES = [
    "comparable_event_rate_per_30d",
    "maximum_magnitude",
    "median_depth_km",
    "spatial_dispersion_km",
    "log10_total_energy_j",
]


@dataclass(frozen=True)
class RegimeResult:
    assignments: pd.DataFrame
    transition_matrix: pd.DataFrame
    current_regime: int | None
    current_label: str
    cluster_count: int
    confidence: float | None


def _label_regime(centre: pd.Series, medians: pd.Series) -> str:
    rate = centre.get("comparable_event_rate_per_30d", np.nan)
    mag = centre.get("maximum_magnitude", np.nan)
    dispersion = centre.get("spatial_dispersion_km", np.nan)
    energy = centre.get("log10_total_energy_j", np.nan)
    high_rate = np.isfinite(rate) and rate > medians.get("comparable_event_rate_per_30d", np.inf)
    high_mag = np.isfinite(mag) and mag > medians.get("maximum_magnitude", np.inf)
    concentrated = np.isfinite(dispersion) and dispersion < medians.get("spatial_dispersion_km", -np.inf)
    high_energy = np.isfinite(energy) and energy > medians.get("log10_total_energy_j", np.inf)
    if high_rate and concentrated:
        return "Atividade concentrada"
    if high_rate and high_energy:
        return "Atividade regional elevada"
    if high_mag and not high_rate:
        return "Eventos esparsos de maior magnitude"
    if high_rate:
        return "Atividade distribuída"
    return "Background de baixa atividade"


def infer_regimes(fingerprints: pd.DataFrame, max_clusters: int = 5, minimum_rows: int = 30) -> RegimeResult:
    data = fingerprints.copy().sort_values("window_end")
    usable = [feature for feature in REGIME_FEATURES if feature in data.columns]
    if len(data) < minimum_rows or len(usable) < 3:
        return RegimeResult(pd.DataFrame(), pd.DataFrame(), None, "Indisponível", 0, None)
    matrix = data[usable].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    imputer = SimpleImputer(strategy="median")
    x_i = imputer.fit_transform(matrix)
    scaler = RobustScaler().fit(x_i)
    x = scaler.transform(x_i)

    best_model = None; best_score = -np.inf
    max_k = min(max_clusters, max(2, len(data)//10))
    for k in range(2, max_k + 1):
        model = KMeans(n_clusters=k, random_state=42, n_init=20).fit(x)
        if len(set(model.labels_)) < 2:
            continue
        score = silhouette_score(x, model.labels_)
        if score > best_score:
            best_score = score; best_model = model
    if best_model is None:
        return RegimeResult(pd.DataFrame(), pd.DataFrame(), None, "Indisponível", 0, None)

    result = data[["window_start", "window_end"]].copy()
    result["regime"] = best_model.labels_
    distances = best_model.transform(x)
    assigned = distances[np.arange(len(distances)), best_model.labels_]
    nearest_alt = np.partition(distances, 1, axis=1)[:, 1]
    confidence = np.clip(1.0 - assigned / np.maximum(nearest_alt, 1e-9), 0.0, 1.0)
    result["regime_confidence"] = confidence

    centres_raw = pd.DataFrame(
        scaler.inverse_transform(best_model.cluster_centers_), columns=usable
    )
    medians = matrix.median(numeric_only=True)
    labels = {i: _label_regime(centres_raw.iloc[i], medians) for i in range(best_model.n_clusters)}
    result["regime_label"] = result["regime"].map(labels)

    transitions = pd.crosstab(result["regime"].shift(1), result["regime"], normalize="index")
    transitions.index.name = "From"; transitions.columns.name = "To"
    current = int(result.iloc[-1]["regime"])
    return RegimeResult(
        assignments=result,
        transition_matrix=transitions,
        current_regime=current,
        current_label=labels[current],
        cluster_count=int(best_model.n_clusters),
        confidence=float(result.iloc[-1]["regime_confidence"]),
    )
