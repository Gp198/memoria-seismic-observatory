from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from sklearn.covariance import MinCovDet
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler


DEFAULT_ANOMALY_FEATURES = [
    "comparable_event_rate_per_30d",
    "maximum_magnitude",
    "mean_magnitude",
    "median_depth_km",
    "depth_std_km",
    "spatial_dispersion_km",
    "log10_total_energy_j",
]

FEATURE_LABELS = {
    "comparable_event_rate_per_30d": "Taxa sísmica",
    "maximum_magnitude": "Magnitude máxima",
    "mean_magnitude": "Magnitude média",
    "median_depth_km": "Profundidade mediana",
    "depth_std_km": "Variabilidade da profundidade",
    "spatial_dispersion_km": "Dispersão espacial",
    "log10_total_energy_j": "Energia sísmica",
}


@dataclass(frozen=True)
class AnomalyComponent:
    name: str
    score: float
    triggered: bool
    detail: str


@dataclass(frozen=True)
class AnomalyAssessment:
    score: float
    level: str
    statistical_anomaly: bool
    tectonic_interpretation: str
    persistence_windows: int
    method_agreement: int
    method_total: int
    components: tuple[AnomalyComponent, ...]
    reference_windows: int
    data_quality: float | None

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["components"] = [asdict(component) for component in self.components]
        return value


def robust_zscore(value: float, history: np.ndarray) -> float:
    history = np.asarray(history, dtype=float)
    history = history[np.isfinite(history)]
    if len(history) < 5 or not np.isfinite(value):
        return np.nan
    median = float(np.median(history))
    mad = float(np.median(np.abs(history - median)))
    if mad <= 1e-12:
        std = float(np.std(history))
        return 0.0 if std <= 1e-12 else float((value - median) / std)
    return float(0.67448975 * (value - median) / mad)


def _univariate_component(history: pd.DataFrame, target: pd.Series, features: list[str]) -> AnomalyComponent:
    scores = []
    labels = []
    for feature in features:
        if feature not in history or feature not in target.index:
            continue
        target_value = pd.to_numeric(pd.Series([target.get(feature)]), errors="coerce").iloc[0]
        values = pd.to_numeric(history[feature], errors="coerce").to_numpy(dtype=float)
        z = robust_zscore(float(target_value) if pd.notna(target_value) else np.nan, values)
        if np.isfinite(z):
            scores.append(min(abs(z) / 4.0, 1.0))
            labels.append((FEATURE_LABELS.get(feature, feature), z))
    if not scores:
        return AnomalyComponent("Robust univariate", 0.0, False, "Sem variáveis suficientes.")
    score = float(np.mean(sorted(scores, reverse=True)[:3]) * 100.0)
    top = sorted(labels, key=lambda item: abs(item[1]), reverse=True)[:3]
    detail = "; ".join(f"{label}: zᵣ={z:.2f}" for label, z in top)
    return AnomalyComponent("Robust univariate", score, score >= 60.0, detail)


def _mahalanobis_component(history: pd.DataFrame, target: pd.Series, features: list[str]) -> AnomalyComponent:
    usable = [feature for feature in features if feature in history and feature in target.index]
    if len(usable) < 3 or len(history) < max(20, len(usable) * 4):
        return AnomalyComponent("Robust Mahalanobis", 0.0, False, "Amostra insuficiente.")
    x = history[usable].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    t = pd.DataFrame([{feature: target.get(feature) for feature in usable}]).apply(pd.to_numeric, errors="coerce")
    imputer = SimpleImputer(strategy="median")
    x_i = imputer.fit_transform(x); t_i = imputer.transform(t)
    scaler = RobustScaler().fit(x_i)
    x_s = scaler.transform(x_i); t_s = scaler.transform(t_i)[0]
    try:
        model = MinCovDet(random_state=42, support_fraction=0.8).fit(x_s)
        distances = model.mahalanobis(x_s)
        target_distance = float(model.mahalanobis([t_s])[0])
    except ValueError:
        centre = np.median(x_s, axis=0)
        distances = np.sum((x_s - centre) ** 2, axis=1)
        target_distance = float(np.sum((t_s - centre) ** 2))
    percentile = float(np.mean(distances <= target_distance))
    score = percentile * 100.0
    return AnomalyComponent(
        "Robust Mahalanobis",
        score,
        percentile >= 0.95,
        f"Distância multivariada no percentil {percentile:.1%} da referência.",
    )


def _isolation_component(history: pd.DataFrame, target: pd.Series, features: list[str]) -> AnomalyComponent:
    usable = [feature for feature in features if feature in history and feature in target.index]
    if len(usable) < 3 or len(history) < 40:
        return AnomalyComponent("Isolation Forest", 0.0, False, "Amostra insuficiente.")
    x = history[usable].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    t = pd.DataFrame([{feature: target.get(feature) for feature in usable}]).apply(pd.to_numeric, errors="coerce")
    imputer = SimpleImputer(strategy="median")
    x_i = imputer.fit_transform(x); t_i = imputer.transform(t)
    scaler = RobustScaler().fit(x_i)
    x_s = scaler.transform(x_i); t_s = scaler.transform(t_i)
    model = IsolationForest(n_estimators=200, contamination="auto", random_state=42).fit(x_s)
    reference = -model.score_samples(x_s)
    target_score = float(-model.score_samples(t_s)[0])
    percentile = float(np.mean(reference <= target_score))
    score = percentile * 100.0
    return AnomalyComponent(
        "Isolation Forest",
        score,
        percentile >= 0.95,
        f"Score de isolamento no percentil {percentile:.1%}.",
    )


def _change_component(series: pd.Series) -> AnomalyComponent:
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) < 20:
        return AnomalyComponent("CUSUM/EWMA", 0.0, False, "Série temporal insuficiente.")
    reference = values[:-1]
    centre = float(np.median(reference)); mad = float(np.median(np.abs(reference - centre)))
    scale = max(1.4826 * mad, float(np.std(reference)), 1e-6)
    standardized = (values - centre) / scale
    k = 0.5
    pos = 0.0; neg = 0.0; max_signal = 0.0
    for value in standardized:
        pos = max(0.0, pos + value - k)
        neg = min(0.0, neg + value + k)
        max_signal = max(max_signal, pos, abs(neg))
    ewma = standardized[0]
    for value in standardized[1:]:
        ewma = 0.25 * value + 0.75 * ewma
    score = float(np.clip(max(max_signal / 8.0, abs(ewma) / 3.0), 0.0, 1.0) * 100.0)
    return AnomalyComponent("CUSUM/EWMA", score, score >= 60.0, f"Sinal acumulado={max_signal:.2f}; EWMA={ewma:.2f}σ.")


def _persistence(fingerprints: pd.DataFrame, feature: str, lookback: int = 6) -> tuple[int, float]:
    if feature not in fingerprints or len(fingerprints) < 10:
        return 0, 0.0
    ordered = fingerprints.sort_values("window_end")
    values = pd.to_numeric(ordered[feature], errors="coerce")
    history = values.iloc[:-lookback].dropna().to_numpy(dtype=float)
    recent = values.iloc[-lookback:].to_numpy(dtype=float)
    if len(history) < 10:
        return 0, 0.0
    threshold = float(np.quantile(history, 0.9))
    flags = np.isfinite(recent) & (recent >= threshold)
    persistence = 0
    for flag in flags[::-1]:
        if flag:
            persistence += 1
        else:
            break
    return persistence, float(np.mean(flags))


def assess_anomaly(
    fingerprints: pd.DataFrame,
    features: list[str] | None = None,
    minimum_history: int = 30,
) -> AnomalyAssessment:
    if fingerprints.empty:
        return AnomalyAssessment(0.0, "Indisponível", False, "Sem dados.", 0, 0, 0, tuple(), 0, None)
    data = fingerprints.copy().sort_values("window_end")
    target = data.iloc[-1]
    epoch = str(target.get("comparison_epoch", ""))
    history = data.iloc[:-1]
    if epoch and "comparison_epoch" in history:
        epoch_history = history[history["comparison_epoch"].astype(str) == epoch]
        if len(epoch_history) >= minimum_history:
            history = epoch_history
    features = features or DEFAULT_ANOMALY_FEATURES

    components = [
        _univariate_component(history, target, features),
        _mahalanobis_component(history, target, features),
        _isolation_component(history, target, features),
        _change_component(data.get("comparable_event_rate_per_30d", pd.Series(dtype=float))),
    ]
    persistence_windows, persistence_fraction = _persistence(data, "comparable_event_rate_per_30d")
    persistence_score = min(100.0, persistence_fraction * 100.0 + min(persistence_windows, 4) * 10.0)
    components.append(AnomalyComponent(
        "Persistência",
        persistence_score,
        persistence_windows >= 3,
        f"{persistence_windows} janelas consecutivas acima do P90; {persistence_fraction:.0%} das janelas recentes acima do P90.",
    ))

    scores = np.asarray([component.score for component in components], dtype=float)
    weights = np.asarray([0.24, 0.26, 0.20, 0.18, 0.12], dtype=float)
    overall = float(np.average(scores, weights=weights))
    agreement = int(sum(component.triggered for component in components))
    statistical_anomaly = agreement >= 3 and overall >= 60.0
    if overall >= 80 and agreement >= 4:
        level = "Elevada"
    elif statistical_anomaly:
        level = "Moderada"
    elif overall >= 45:
        level = "Em observação"
    else:
        level = "Dentro da referência"

    quality = pd.to_numeric(pd.Series([target.get("data_quality_score")]), errors="coerce").iloc[0]
    tectonic = (
        "Anomalia sísmica estatística detetada; interpretação tectónica requer evidência geofísica independente."
        if statistical_anomaly
        else "Sem evidência estatística suficiente para interpretação tectónica."
    )
    return AnomalyAssessment(
        score=overall,
        level=level,
        statistical_anomaly=statistical_anomaly,
        tectonic_interpretation=tectonic,
        persistence_windows=persistence_windows,
        method_agreement=agreement,
        method_total=len(components),
        components=tuple(components),
        reference_windows=int(len(history)),
        data_quality=float(quality) if pd.notna(quality) else None,
    )
