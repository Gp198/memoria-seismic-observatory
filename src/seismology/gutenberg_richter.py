from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.quality.completeness import estimate_magnitude_completeness
from src.quality.epochs import EPOCH_BY_KEY, assign_observation_epoch, observation_epoch_for_timestamp
from src.quality.magnitude import (
    normalise_magnitude_type,
    validated_magnitude_mask,
)


@dataclass(frozen=True)
class BValueEstimate:
    b_value: float | None
    sigma: float | None
    mc: float | None
    event_count: int
    sufficient_data: bool
    method: str = "Aki maximum-likelihood"


@dataclass(frozen=True)
class BValueScientificAssessment:
    """Auditable b-value result with an explicit magnitude-population contract.

    `sigma` in `estimate` is sampling/statistical uncertainty only.  It must not
    be presented as total scientific uncertainty when catalogue scale,
    completeness or conversion uncertainty remains material.
    """

    estimate: BValueEstimate
    status: str
    population_label: str
    magnitude_column: str
    magnitude_types: tuple[str, ...]
    sources: tuple[str, ...]
    epoch_key: str | None
    epoch_label: str | None
    population_event_count: int
    validated_population: bool
    systematic_uncertainty_dominant: bool
    warning: str


@dataclass(frozen=True)
class BValuePopulation:
    frame: pd.DataFrame
    magnitude_column: str
    mc: float | None
    status: str
    population_label: str
    magnitude_types: tuple[str, ...]
    sources: tuple[str, ...]
    epoch_key: str | None
    epoch_label: str | None
    validated_population: bool
    systematic_uncertainty_dominant: bool
    warning: str


def estimate_b_value(
    magnitudes: pd.Series | np.ndarray | list[float],
    mc: float | None,
    bin_width: float = 0.1,
    minimum_events: int = 25,
) -> BValueEstimate:
    values = pd.to_numeric(pd.Series(magnitudes), errors="coerce").dropna()
    if mc is None or not np.isfinite(float(mc)):
        return BValueEstimate(None, None, None, int(len(values)), False)

    complete = values[values >= float(mc)].astype(float).to_numpy()
    n = int(len(complete))
    if n < minimum_events:
        return BValueEstimate(None, None, float(mc), n, False)

    denominator = float(np.mean(complete) - (float(mc) - bin_width / 2.0))
    if denominator <= 0:
        return BValueEstimate(None, None, float(mc), n, False)

    b_value = float(np.log10(np.e) / denominator)
    if n > 1:
        variance_sum = float(np.sum((complete - np.mean(complete)) ** 2))
        sigma = float(2.30 * b_value * b_value * np.sqrt(variance_sum / (n * (n - 1))))
    else:
        sigma = None
    return BValueEstimate(b_value, sigma, float(mc), n, True)


def _current_epoch_subset(events: pd.DataFrame) -> tuple[pd.DataFrame, str | None, str | None]:
    frame = events.copy()
    frame["origin_time_utc"] = pd.to_datetime(frame.get("origin_time_utc"), utc=True, errors="coerce")
    frame = frame.dropna(subset=["origin_time_utc"])
    if frame.empty:
        return frame, None, None
    latest = frame["origin_time_utc"].max()
    epoch = observation_epoch_for_timestamp(latest)
    frame = assign_observation_epoch(frame)
    frame = frame.loc[frame["observation_epoch"].eq(epoch.key)].copy()
    return frame, epoch.key, epoch.label


def select_scientific_b_value_population(
    events: pd.DataFrame,
    magnitude_policy: str,
    *,
    minimum_population_events: int = 50,
) -> BValuePopulation:
    """Select a defensible population before estimating Gutenberg–Richter b.

    Validated policy: reviewed identity/conversion magnitudes may be analysed in
    the current observation epoch using `magnitude_comparable`.

    Operational policy: the mixed comparable catalogue is *not* used directly.
    Instead, the dominant source + original magnitude-scale cohort in the
    current epoch is selected, and b is estimated from the original numeric
    magnitude on that coherent cohort.  This remains exploratory because
    network/practice changes within the epoch may still affect completeness.
    """
    frame, epoch_key, epoch_label = _current_epoch_subset(events)
    if frame.empty:
        return BValuePopulation(
            frame=frame,
            magnitude_column="magnitude_comparable",
            mc=None,
            status="insufficient",
            population_label="Sem população elegível",
            magnitude_types=tuple(),
            sources=tuple(),
            epoch_key=epoch_key,
            epoch_label=epoch_label,
            validated_population=False,
            systematic_uncertainty_dominant=True,
            warning="Não existem eventos com data válida na época de observação atual.",
        )

    for column in ("magnitude_original_value", "magnitude_comparable"):
        if column not in frame.columns:
            frame[column] = np.nan
    if "magnitude_original_type" not in frame.columns:
        frame["magnitude_original_type"] = frame.get("magnitude_type", pd.Series(index=frame.index, dtype=object))
    if "source" not in frame.columns:
        frame["source"] = "UNKNOWN"

    frame["magnitude_original_type_norm"] = frame["magnitude_original_type"].map(normalise_magnitude_type)
    frame["source_norm"] = frame["source"].fillna("UNKNOWN").astype(str).str.strip().replace("", "UNKNOWN")

    if magnitude_policy == "validated":
        mask = validated_magnitude_mask(frame)
        selected = frame.loc[mask].copy()
        selected["magnitude_comparable"] = pd.to_numeric(selected["magnitude_comparable"], errors="coerce")
        selected = selected.dropna(subset=["magnitude_comparable"])
        types = tuple(sorted(selected["magnitude_original_type_norm"].dropna().astype(str).unique().tolist()))
        sources = tuple(sorted(selected["source_norm"].dropna().astype(str).unique().tolist()))
        mc_est = estimate_magnitude_completeness(selected["magnitude_comparable"], minimum_events=max(25, minimum_population_events // 2))
        epoch_floor = EPOCH_BY_KEY[epoch_key].minimum_comparable_magnitude if epoch_key in EPOCH_BY_KEY else None
        mc = max(float(mc_est.mc), float(epoch_floor)) if mc_est.mc is not None and epoch_floor is not None else mc_est.mc
        enough = len(selected) >= minimum_population_events and mc is not None
        warning = (
            "População composta apenas por magnitudes/conversões revistas. O σ apresentado continua a representar apenas incerteza estatística; "
            "heterogeneidade residual de rede, localização e conversão deve ser tratada separadamente."
            if enough
            else "Cobertura validada insuficiente para estimar b de forma robusta na época atual."
        )
        return BValuePopulation(
            frame=selected,
            magnitude_column="magnitude_comparable",
            mc=float(mc) if mc is not None else None,
            status="validated" if enough else "insufficient",
            population_label=f"Validada · {epoch_label or 'época atual'}",
            magnitude_types=types,
            sources=sources,
            epoch_key=epoch_key,
            epoch_label=epoch_label,
            validated_population=True,
            systematic_uncertainty_dominant=not enough or len(types) > 1 or len(sources) > 1,
            warning=warning,
        )

    # Operational mode: never estimate b directly from a mixture of magnitude scales.
    candidate = frame.copy()
    candidate["magnitude_original_value"] = pd.to_numeric(candidate["magnitude_original_value"], errors="coerce")
    candidate = candidate.dropna(subset=["magnitude_original_value"])
    if candidate.empty:
        return BValuePopulation(
            frame=candidate,
            magnitude_column="magnitude_original_value",
            mc=None,
            status="insufficient",
            population_label="Operacional · sem escala coerente",
            magnitude_types=tuple(),
            sources=tuple(),
            epoch_key=epoch_key,
            epoch_label=epoch_label,
            validated_population=False,
            systematic_uncertainty_dominant=True,
            warning="Não existem magnitudes originais suficientes para construir uma coorte homogénea.",
        )

    counts = (
        candidate.groupby(["source_norm", "magnitude_original_type_norm"], dropna=False)
        .size()
        .sort_values(ascending=False)
    )
    source, mag_type = counts.index[0]
    selected = candidate.loc[
        candidate["source_norm"].eq(source)
        & candidate["magnitude_original_type_norm"].eq(mag_type)
    ].copy()
    mc_est = estimate_magnitude_completeness(selected["magnitude_original_value"], minimum_events=max(25, minimum_population_events // 2))
    epoch_floor = EPOCH_BY_KEY[epoch_key].minimum_comparable_magnitude if epoch_key in EPOCH_BY_KEY else None
    mc = max(float(mc_est.mc), float(epoch_floor)) if mc_est.mc is not None and epoch_floor is not None else mc_est.mc
    enough = len(selected) >= minimum_population_events and mc is not None
    warning = (
        "b exploratório calculado apenas numa coorte coerente de fonte + escala original; não usa a mistura operacional de escalas. "
        "O σ é apenas estatístico e não inclui mudanças de rede, prática de magnitude, Mc ou outros erros sistemáticos."
        if enough
        else "A maior coorte fonte + escala da época atual não tem cobertura suficiente para um b-value responsável."
    )
    return BValuePopulation(
        frame=selected,
        magnitude_column="magnitude_original_value",
        mc=float(mc) if mc is not None else None,
        status="scale_coherent_exploratory" if enough else "insufficient",
        population_label=f"Exploratória · {source} {mag_type} · {epoch_label or 'época atual'}",
        magnitude_types=(str(mag_type),),
        sources=(str(source),),
        epoch_key=epoch_key,
        epoch_label=epoch_label,
        validated_population=False,
        systematic_uncertainty_dominant=True,
        warning=warning,
    )


def estimate_scientific_b_value(
    events: pd.DataFrame,
    magnitude_policy: str,
    *,
    minimum_events: int = 50,
) -> tuple[BValueScientificAssessment, BValuePopulation]:
    population = select_scientific_b_value_population(
        events,
        magnitude_policy,
        minimum_population_events=minimum_events,
    )
    estimate = estimate_b_value(
        population.frame.get(population.magnitude_column, pd.Series(dtype=float)),
        population.mc,
        minimum_events=minimum_events,
    )
    status = population.status if estimate.sufficient_data else "insufficient"
    assessment = BValueScientificAssessment(
        estimate=estimate,
        status=status,
        population_label=population.population_label,
        magnitude_column=population.magnitude_column,
        magnitude_types=population.magnitude_types,
        sources=population.sources,
        epoch_key=population.epoch_key,
        epoch_label=population.epoch_label,
        population_event_count=int(len(population.frame)),
        validated_population=population.validated_population,
        systematic_uncertainty_dominant=population.systematic_uncertainty_dominant,
        warning=population.warning,
    )
    return assessment, population


def format_b_sigma(sigma: float | None) -> str:
    """Avoid displaying false zero precision for very small sampling σ."""
    if sigma is None or not np.isfinite(float(sigma)):
        return "σ n/d"
    value = float(sigma)
    if value < 0.005:
        return "σ estatístico <0,01"
    return f"σ estatístico {value:.2f}"


def rolling_b_value(
    events: pd.DataFrame,
    mc: float,
    window_events: int = 100,
    step_events: int = 20,
    minimum_events: int = 25,
    magnitude_column: str = "magnitude_comparable",
) -> pd.DataFrame:
    frame = events.copy()
    frame["origin_time_utc"] = pd.to_datetime(frame["origin_time_utc"], utc=True, errors="coerce")
    if magnitude_column not in frame.columns:
        return pd.DataFrame()
    frame[magnitude_column] = pd.to_numeric(frame[magnitude_column], errors="coerce")
    frame = frame.dropna(subset=["origin_time_utc", magnitude_column])
    frame = frame[frame[magnitude_column] >= mc].sort_values("origin_time_utc")
    rows: list[dict[str, object]] = []
    if len(frame) < minimum_events:
        return pd.DataFrame(rows)

    window_events = max(minimum_events, int(window_events))
    step_events = max(1, int(step_events))
    for end in range(window_events, len(frame) + 1, step_events):
        sample = frame.iloc[end - window_events:end]
        estimate = estimate_b_value(sample[magnitude_column], mc, minimum_events=minimum_events)
        rows.append({
            "window_start": sample["origin_time_utc"].min(),
            "window_end": sample["origin_time_utc"].max(),
            "b_value": estimate.b_value,
            "b_sigma": estimate.sigma,
            "mc": mc,
            "event_count": estimate.event_count,
        })
    return pd.DataFrame(rows)
