from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler

from src.features.fingerprints import FINGERPRINT_FEATURES

FEATURE_WEIGHTS = {
    "comparable_event_count": 1.00,
    "comparable_event_rate_per_30d": 1.10,
    "maximum_magnitude": 1.15,
    "mean_magnitude": 0.85,
    "median_depth_km": 0.70,
    "depth_std_km": 0.60,
    "spatial_dispersion_km": 0.85,
    "log10_total_energy_j": 1.00,
    "days_since_previous_m3": 0.70,
    "catalogue_completeness_mc": 0.70,
    "data_quality_score": 0.55,
}

FEATURE_LABELS_PT = {
    "comparable_event_count": "Eventos comparáveis",
    "comparable_event_rate_per_30d": "Taxa comparável de eventos",
    "maximum_magnitude": "Magnitude máxima",
    "mean_magnitude": "Magnitude média",
    "median_depth_km": "Profundidade mediana",
    "depth_std_km": "Variabilidade da profundidade",
    "spatial_dispersion_km": "Dispersão espacial",
    "log10_total_energy_j": "Energia sísmica estimada",
    "days_since_previous_m3": "Dias desde o último M≥3",
    "catalogue_completeness_mc": "Magnitude de completude",
    "data_quality_score": "Qualidade dos dados",
}

SOURCE_SHARE_COLUMNS = [
    "source_share_ipma",
    "source_share_isc",
    "source_share_ahead",
    "source_share_other",
]
COVERAGE_COLUMNS = [
    "magnitude_coverage_ratio",
    "depth_coverage_ratio",
    "location_coverage_ratio",
]


@dataclass
class SimilarityResult:
    target: pd.Series
    neighbours: pd.DataFrame
    feature_differences: pd.DataFrame
    features: list[str]
    family_gap_days: int
    family_buffer_days: int
    target_epoch: str
    comparison_pool_size: int
    family_method: str

    @property
    def diversity_days(self) -> int:
        return self.family_gap_days


def _select_usable_features(
    history: pd.DataFrame,
    target: pd.Series,
    requested_features: list[str],
) -> list[str]:
    usable = []
    for feature in requested_features:
        if feature not in history.columns or feature not in target.index:
            continue
        values = (
            pd.to_numeric(history[feature], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if len(values) >= 3 and values.nunique() >= 2:
            usable.append(feature)
    return usable


def _prepare_matrix(history, target, features):
    training = (
        history[features]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .astype(float)
    )
    target_frame = (
        pd.DataFrame(
            [{feature: target.get(feature, np.nan) for feature in features}]
        )
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .astype(float)
    )
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    training_imputed = imputer.fit_transform(training)
    target_imputed = imputer.transform(target_frame)

    lower = np.nanquantile(training_imputed, 0.025, axis=0)
    upper = np.nanquantile(training_imputed, 0.975, axis=0)
    equal = np.isclose(lower, upper)
    lower[equal] = np.nanmin(training_imputed[:, equal], axis=0)
    upper[equal] = np.nanmax(training_imputed[:, equal], axis=0)

    scaler = RobustScaler(
        quantile_range=(10.0, 90.0),
        unit_variance=True,
    )
    training_scaled = np.clip(
        scaler.fit_transform(np.clip(training_imputed, lower, upper)),
        -6.0,
        6.0,
    )
    target_scaled = np.clip(
        scaler.transform(np.clip(target_imputed, lower, upper))[0],
        -6.0,
        6.0,
    )
    return training_scaled, target_scaled, imputer, scaler, lower, upper


def _numeric_compatibility(history, target, column, default, scale):
    target_value = pd.to_numeric(
        pd.Series([target.get(column)]), errors="coerce"
    ).iloc[0]
    history_values = pd.to_numeric(
        history.get(column, pd.Series(np.nan, index=history.index)),
        errors="coerce",
    ).to_numpy(dtype=float)
    if pd.isna(target_value):
        return np.full(len(history), default)
    differences = np.abs(history_values - float(target_value))
    return np.where(
        np.isfinite(differences),
        np.exp(-differences / max(scale, 1e-6)),
        default,
    )


def _coverage_compatibility(history, target):
    parts = []
    for column in COVERAGE_COLUMNS:
        target_value = pd.to_numeric(
            pd.Series([target.get(column)]), errors="coerce"
        ).iloc[0]
        values = pd.to_numeric(
            history.get(column, pd.Series(np.nan, index=history.index)),
            errors="coerce",
        ).to_numpy(dtype=float)
        if pd.isna(target_value):
            parts.append(np.full(len(history), 0.65))
        else:
            difference = np.abs(values - float(target_value))
            parts.append(
                np.where(
                    np.isfinite(difference),
                    np.clip(1.0 - difference, 0.05, 1.0),
                    0.65,
                )
            )
    return np.mean(np.vstack(parts), axis=0)


def _source_profile_compatibility(history, target):
    target_vector = np.asarray(
        [
            pd.to_numeric(
                pd.Series([target.get(column, 0.0)]),
                errors="coerce",
            ).fillna(0.0).iloc[0]
            for column in SOURCE_SHARE_COLUMNS
        ],
        dtype=float,
    )
    history_matrix = np.column_stack(
        [
            pd.to_numeric(
                history.get(column, pd.Series(0.0, index=history.index)),
                errors="coerce",
            )
            .fillna(0.0)
            .to_numpy(dtype=float)
            for column in SOURCE_SHARE_COLUMNS
        ]
    )
    target_norm = np.linalg.norm(target_vector)
    norms = np.linalg.norm(history_matrix, axis=1)
    denominator = norms * target_norm
    if target_norm == 0:
        return np.full(len(history), 0.5)
    cosine = np.divide(
        history_matrix @ target_vector,
        denominator,
        out=np.zeros(len(history)),
        where=denominator > 0,
    )
    return np.clip(cosine, 0.05, 1.0)


def _comparability_scores(history, target):
    quality = _numeric_compatibility(
        history, target, "data_quality_score", 0.60, 0.18
    )
    completeness = _numeric_compatibility(
        history, target, "catalogue_completeness_mc", 0.55, 0.65
    )
    threshold = _numeric_compatibility(
        history, target, "comparison_magnitude_threshold", 0.50, 0.50
    )
    coverage = _coverage_compatibility(history, target)
    source_profile = _source_profile_compatibility(history, target)

    components = np.column_stack(
        [quality, completeness, threshold, coverage, source_profile]
    )
    weights = np.asarray([0.20, 0.20, 0.15, 0.20, 0.25])
    overall = np.exp(
        np.sum(
            weights * np.log(np.clip(components, 0.05, 1.0)),
            axis=1,
        )
    )
    return {
        "comparability_score": np.clip(overall, 0.05, 1.0),
        "quality_compatibility": quality,
        "completeness_compatibility": completeness,
        "threshold_compatibility": threshold,
        "coverage_compatibility": coverage,
        "source_profile_compatibility": source_profile,
    }


def _intervals_overlap(
    start_a: pd.Timestamp,
    end_a: pd.Timestamp,
    start_b: pd.Timestamp,
    end_b: pd.Timestamp,
    buffer_days: int,
) -> bool:
    buffer = pd.Timedelta(days=max(0, int(buffer_days)))
    return start_a <= end_b + buffer and end_a >= start_b - buffer


def _select_temporal_families(
    candidates: pd.DataFrame,
    k: int,
    family_radius_days: int,
    family_buffer_days: int,
) -> pd.DataFrame:
    ranked = candidates.sort_values("adjusted_distance").copy()
    selected: list[pd.Series] = []
    half_width = max(1, int(np.ceil(family_radius_days / 2)))
    all_ends = pd.to_datetime(ranked["window_end"], utc=True)

    for _, representative in ranked.iterrows():
        centre = pd.to_datetime(representative["window_end"], utc=True)
        members = ranked.loc[
            (all_ends - centre).abs().dt.days <= half_width
        ]
        family_start = pd.to_datetime(
            members["window_start"].min(), utc=True
        )
        family_end = pd.to_datetime(
            members["window_end"].max(), utc=True
        )

        if any(
            _intervals_overlap(
                family_start,
                family_end,
                pd.to_datetime(item["family_start"], utc=True),
                pd.to_datetime(item["family_end"], utc=True),
                family_buffer_days,
            )
            for item in selected
        ):
            continue

        chosen = representative.copy()
        chosen["family_start"] = family_start
        chosen["family_end"] = family_end
        chosen["family_window_count"] = int(len(members))
        chosen["family_radius_days"] = int(family_radius_days)
        chosen["family_buffer_days"] = int(family_buffer_days)
        chosen["family_id"] = (
            f"FAM-{family_start.strftime('%Y%m%d')}"
            f"-{family_end.strftime('%Y%m%d')}"
        )
        selected.append(chosen)
        if len(selected) >= k:
            break

    if not selected:
        raise ValueError(
            "Não foi possível construir famílias temporais independentes."
        )

    result = pd.DataFrame(selected).sort_values(
        "adjusted_distance"
    ).reset_index(drop=True)
    result["analogue_rank"] = np.arange(1, len(result) + 1)
    result["episode_id"] = result["window_end"].map(
        lambda value: f"EPI-{pd.to_datetime(value).strftime('%Y%m%d')}"
    )
    return result



def _adaptive_regime_ids(
    candidates: pd.DataFrame,
    maximum_span_days: int,
    change_threshold: float = 3.5,
) -> pd.Series:
    ordered = candidates.sort_values("window_end").copy()
    feature_columns = [
        column
        for column in [
            "comparable_event_rate_per_30d",
            "maximum_magnitude",
            "log10_total_energy_j",
            "spatial_dispersion_km",
        ]
        if column in ordered.columns
    ]
    if not feature_columns:
        return pd.Series(
            np.arange(len(ordered)),
            index=ordered.index,
            dtype="int64",
        )

    matrix = (
        ordered[feature_columns]
        .apply(pd.to_numeric, errors="coerce")
        .interpolate(limit_direction="both")
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    differences = np.diff(matrix, axis=0)
    if len(differences) == 0:
        return pd.Series(0, index=ordered.index, dtype="int64")
    centres = np.nanmedian(differences, axis=0)
    mad = np.nanmedian(np.abs(differences - centres), axis=0)
    scales = np.where(mad > 1e-9, 1.4826 * mad, np.nanstd(differences, axis=0))
    scales = np.where(scales > 1e-9, scales, 1.0)
    change_scores = np.max(
        np.abs((differences - centres) / scales),
        axis=1,
    )

    dates = pd.to_datetime(ordered["window_end"], utc=True)
    regime_ids = np.zeros(len(ordered), dtype=int)
    regime_id = 0
    regime_start = dates.iloc[0]
    maximum_gap = max(31, int(maximum_span_days // 3))

    for position in range(1, len(ordered)):
        gap_days = int((dates.iloc[position] - dates.iloc[position - 1]).days)
        span_days = int((dates.iloc[position] - regime_start).days)
        change = float(change_scores[position - 1])
        if (
            gap_days > maximum_gap
            or change >= float(change_threshold)
            or span_days > int(maximum_span_days)
        ):
            regime_id += 1
            regime_start = dates.iloc[position]
        regime_ids[position] = regime_id

    return pd.Series(regime_ids, index=ordered.index, dtype="int64")


def _select_adaptive_temporal_families(
    candidates: pd.DataFrame,
    k: int,
    maximum_span_days: int,
    family_buffer_days: int,
    change_threshold: float,
) -> pd.DataFrame:
    working = candidates.copy()
    working["adaptive_regime_id"] = _adaptive_regime_ids(
        working,
        maximum_span_days=maximum_span_days,
        change_threshold=change_threshold,
    )
    representatives: list[pd.Series] = []
    for regime_id, members in working.groupby("adaptive_regime_id"):
        representative = members.sort_values("adjusted_distance").iloc[0].copy()
        representative["family_start"] = pd.to_datetime(
            members["window_start"].min(), utc=True
        )
        representative["family_end"] = pd.to_datetime(
            members["window_end"].max(), utc=True
        )
        representative["family_window_count"] = int(len(members))
        representative["family_radius_days"] = int(maximum_span_days)
        representative["family_buffer_days"] = int(family_buffer_days)
        representative["family_change_score"] = float(
            members.get(
                "adaptive_change_score",
                pd.Series(0.0, index=members.index),
            ).max()
        )
        representative["adaptive_regime_id"] = int(regime_id)
        representatives.append(representative)

    ranked = pd.DataFrame(representatives).sort_values("adjusted_distance")
    selected: list[pd.Series] = []
    for _, candidate in ranked.iterrows():
        start = pd.to_datetime(candidate["family_start"], utc=True)
        end = pd.to_datetime(candidate["family_end"], utc=True)
        if any(
            _intervals_overlap(
                start,
                end,
                pd.to_datetime(item["family_start"], utc=True),
                pd.to_datetime(item["family_end"], utc=True),
                family_buffer_days,
            )
            for item in selected
        ):
            continue
        chosen = candidate.copy()
        chosen["family_id"] = (
            f"REG-{start.strftime('%Y%m%d')}"
            f"-{end.strftime('%Y%m%d')}"
        )
        selected.append(chosen)
        if len(selected) >= k:
            break

    if not selected:
        raise ValueError(
            "Não foi possível construir regimes temporais adaptativos independentes."
        )
    result = pd.DataFrame(selected).sort_values("adjusted_distance").reset_index(drop=True)
    result["analogue_rank"] = np.arange(1, len(result) + 1)
    result["episode_id"] = result["window_end"].map(
        lambda value: f"EPI-{pd.to_datetime(value).strftime('%Y%m%d')}"
    )
    result["family_method"] = "adaptive_regime"
    return result

def nearest_states(
    fingerprints: pd.DataFrame,
    domain: str,
    window_days: int,
    target_end=None,
    k: int = 5,
    exclusion_days: int = 365,
    diversity_days: int | None = None,
    family_gap_days: int | None = None,
    family_buffer_days: int | None = None,
    metric: str = "euclidean",
    features=None,
    strict_epoch: bool = True,
    family_method: str = "fixed",
    change_threshold: float = 3.5,
) -> SimilarityResult:
    requested_features = features or FINGERPRINT_FEATURES
    resolved_family_gap = int(
        family_gap_days
        if family_gap_days is not None
        else (
            diversity_days
            if diversity_days is not None
            else max(window_days * 8, 365)
        )
    )
    resolved_family_buffer = int(
        family_buffer_days
        if family_buffer_days is not None
        else max(window_days, 90)
    )

    data = fingerprints[
        (fingerprints["tectonic_domain"] == domain)
        & (fingerprints["window_days"] == window_days)
    ].copy()
    data["window_end"] = pd.to_datetime(
        data["window_end"], utc=True, errors="coerce"
    )
    data["window_start"] = pd.to_datetime(
        data["window_start"], utc=True, errors="coerce"
    )
    data = data.dropna(subset=["window_end"]).sort_values("window_end")
    if data.empty:
        raise ValueError("Não existem fingerprints para a seleção.")

    if target_end is None:
        target = data.iloc[-1]
    else:
        eligible = data[
            data["window_end"] <= pd.to_datetime(target_end, utc=True)
        ]
        if eligible.empty:
            raise ValueError("Não existe fingerprint-alvo elegível.")
        target = eligible.iloc[-1]

    history = data[
        data["window_end"]
        <= target["window_end"] - pd.Timedelta(days=exclusion_days)
    ].copy()
    target_epoch = str(target.get("comparison_epoch", ""))
    if strict_epoch and target_epoch and "comparison_epoch" in history:
        history = history[
            history["comparison_epoch"].astype(str) == target_epoch
        ].copy()

    if len(history) < max(5, k):
        raise ValueError(
            "A época comparável não contém janelas suficientes."
        )

    usable = _select_usable_features(history, target, requested_features)
    if len(usable) < 2:
        raise ValueError("Variáveis comparáveis insuficientes.")

    (
        training_scaled,
        target_scaled,
        imputer,
        scaler,
        lower,
        upper,
    ) = _prepare_matrix(history, target, usable)

    weights = np.asarray(
        [FEATURE_WEIGHTS.get(feature, 1.0) for feature in usable],
        dtype=float,
    )
    weights /= np.mean(weights)
    weighted_training = training_scaled * np.sqrt(weights)
    weighted_target = target_scaled * np.sqrt(weights)

    if metric == "mahalanobis" and len(history) > len(usable) + 2:
        covariance = np.atleast_2d(
            np.cov(weighted_training, rowvar=False)
        )
        inverse = np.linalg.pinv(
            covariance + np.eye(covariance.shape[0]) * 1e-6
        )
        differences = weighted_training - weighted_target
        raw_distances = np.sqrt(
            np.maximum(
                0.0,
                np.einsum(
                    "ij,jk,ik->i",
                    differences,
                    inverse,
                    differences,
                ),
            )
        )
    else:
        raw_distances = np.linalg.norm(
            weighted_training - weighted_target,
            axis=1,
        )

    compatibility = _comparability_scores(history, target)
    history["raw_distance"] = raw_distances
    for column, values in compatibility.items():
        history[column] = values
    history["adjusted_distance"] = (
        history["raw_distance"]
        / np.clip(history["comparability_score"], 0.20, 1.0)
    )
    finite = history["adjusted_distance"].to_numpy(dtype=float)
    finite = finite[np.isfinite(finite)]
    scale = max(float(np.nanmedian(finite)) if len(finite) else 1.0, 1e-6)
    history["similarity"] = np.exp(
        -history["adjusted_distance"] / scale
    )

    if family_method == "adaptive":
        neighbours = _select_adaptive_temporal_families(
            history,
            min(k, len(history)),
            maximum_span_days=resolved_family_gap,
            family_buffer_days=resolved_family_buffer,
            change_threshold=change_threshold,
        )
    else:
        neighbours = _select_temporal_families(
            history,
            min(k, len(history)),
            family_radius_days=resolved_family_gap,
            family_buffer_days=resolved_family_buffer,
        )
        neighbours["family_method"] = "fixed_window"

    values = (
        neighbours[usable]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .astype(float)
    )
    target_values = pd.Series(
        {
            feature: pd.to_numeric(
                pd.Series([target.get(feature)]), errors="coerce"
            ).iloc[0]
            for feature in usable
        },
        dtype=float,
    )
    imputed_neighbours = imputer.transform(values)
    imputed_target = imputer.transform(
        pd.DataFrame([target_values], columns=usable)
    )[0]
    scaled_neighbours = np.clip(
        scaler.transform(np.clip(imputed_neighbours, lower, upper)),
        -6.0,
        6.0,
    )
    scaled_target = np.clip(
        scaler.transform(
            np.clip(imputed_target, lower, upper).reshape(1, -1)
        )[0],
        -6.0,
        6.0,
    )
    absolute = np.abs(scaled_neighbours - scaled_target)
    weighted = absolute * weights

    rows = []
    for row_number, (_, neighbour) in enumerate(neighbours.iterrows()):
        components = weighted[row_number]
        total = float(np.sum(components))
        contributions = (
            components / total * 100.0
            if total > 0
            else np.zeros_like(components)
        )
        for feature_number, feature in enumerate(usable):
            rows.append(
                {
                    "neighbour_window_end": neighbour["window_end"],
                    "episode_id": neighbour["episode_id"],
                    "family_id": neighbour["family_id"],
                    "feature": feature,
                    "feature_label": FEATURE_LABELS_PT.get(
                        feature, feature
                    ),
                    "target_value": target_values[feature],
                    "neighbour_value": neighbour.get(feature),
                    "robust_absolute_difference": float(
                        absolute[row_number, feature_number]
                    ),
                    "weighted_difference": float(
                        weighted[row_number, feature_number]
                    ),
                    "contribution_pct": float(
                        contributions[feature_number]
                    ),
                }
            )

    return SimilarityResult(
        target=target,
        neighbours=neighbours,
        feature_differences=pd.DataFrame(rows),
        features=usable,
        family_gap_days=resolved_family_gap,
        family_buffer_days=resolved_family_buffer,
        target_epoch=target_epoch,
        comparison_pool_size=int(len(history)),
        family_method=str(family_method),
    )
