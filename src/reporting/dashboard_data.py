from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.config import PATHS

EVENT_NUMERIC_COLUMNS = [
    "latitude",
    "longitude",
    "depth_km",
    "magnitude_value",
    "magnitude_comparable",
    "magnitude_original_value",
    "magnitude_conversion_uncertainty",
    "location_uncertainty_km",
    "magnitude_uncertainty",
    "domain_confidence",
    "quality_score",
]

FINGERPRINT_NUMERIC_COLUMNS = [
    "window_days",
    "event_count",
    "event_rate_per_30d",
    "comparable_event_count",
    "comparable_event_rate_per_30d",
    "maximum_magnitude",
    "mean_magnitude",
    "median_depth_km",
    "depth_std_km",
    "spatial_dispersion_km",
    "log10_total_energy_j",
    "days_since_previous_m3",
    "catalogue_completeness_mc",
    "comparison_magnitude_threshold",
    "epoch_catalogue_mc",
    "epoch_event_count",
    "data_quality_score",
    "magnitude_coverage_ratio",
    "depth_coverage_ratio",
    "location_coverage_ratio",
    "source_diversity_score",
    "source_share_ipma",
    "source_share_isc",
    "source_share_ahead",
    "source_share_other",
    "historical_percentile_event_rate",
    "historical_reference_windows",
    "comparable_percentile_event_rate",
    "comparable_reference_windows",
    "comparable_effective_sample_size",
    "comparable_percentile_ci_lower",
    "comparable_percentile_ci_upper",
    "comparable_overlap_factor",
    "comparable_lag1_autocorrelation",
    "historical_effective_sample_size",
    "historical_percentile_ci_lower",
    "historical_percentile_ci_upper",
]


@dataclass(frozen=True)
class TemporalAggregation:
    data: pd.DataFrame
    x_column: str
    title: str
    axis_title: str


def _extract_year(value: object) -> int | None:
    if value is None or value is pd.NaT:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    year = getattr(value, "year", None)
    if year is not None:
        return int(year)
    text = str(value).strip()
    match = re.match(r"^([+-]?\d{4})", text)
    return int(match.group(1)) if match else None


def extract_years(values: pd.Series) -> pd.Series:
    return values.map(_extract_year).astype("Int64")


def _format_datetime(value: object) -> str:
    if value is None or value is pd.NaT:
        return "Data indisponível"
    try:
        if pd.isna(value):
            return "Data indisponível"
    except (TypeError, ValueError):
        pass
    formatter = getattr(value, "strftime", None)
    if callable(formatter):
        try:
            return formatter("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, OverflowError):
            pass
    return str(value)


def _format_month(value: object) -> str:
    year = _extract_year(value)
    month = getattr(value, "month", None)
    if year is not None and month is not None:
        return f"{year:04d}-{int(month):02d}"
    text = str(value)
    return text[:7] if len(text) >= 7 else text


def prepare_dashboard_events(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    origin_values = result.get("origin_time_utc")
    if origin_values is not None:
        if pd.api.types.is_datetime64_any_dtype(origin_values.dtype):
            result["origin_time_utc"] = origin_values
        else:
            parsed = pd.to_datetime(
                origin_values, utc=True, errors="coerce"
            )
            result["origin_time_utc"] = parsed.where(
                parsed.notna(), origin_values
            )
    if "ingested_at_utc" in result.columns:
        result["ingested_at_utc"] = pd.to_datetime(
            result["ingested_at_utc"], utc=True, errors="coerce"
        )
    for column in EVENT_NUMERIC_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column], errors="coerce"
            ).astype("float64")
    for column in [
        "source",
        "location_text",
        "tectonic_domain",
        "magnitude_type",
        "record_status",
        "magnitude_original_type",
        "magnitude_homogenization_method",
        "magnitude_homogenization_status",
        "cluster_role",
        "declustering_method",
        "declustering_exclusion_reason",
    ]:
        if column in result.columns:
            result[column] = (
                result[column].astype("string").fillna("").astype(object)
            )
    return result


def prepare_dashboard_fingerprints(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ["window_start", "window_end"]:
        if column in result.columns:
            result[column] = pd.to_datetime(
                result[column], utc=True, errors="coerce"
            )
    for column in FINGERPRINT_NUMERIC_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column], errors="coerce"
            ).astype("float64")
    for text_column in ["catalogue_mode", "magnitude_policy", "comparison_epoch", "comparison_epoch_label", "dominant_source"]:
        if text_column in result.columns:
            result[text_column] = result[text_column].astype("string").fillna("").astype(object)
    if "tectonic_domain" in result.columns:
        result["tectonic_domain"] = (
            result["tectonic_domain"].astype("string").fillna("").astype(object)
        )
    return result


def calendar_span_years(values: pd.Series) -> int:
    years = extract_years(values).dropna()
    if years.empty:
        return 0
    return int(years.max() - years.min())


def build_temporal_aggregation(frame: pd.DataFrame) -> TemporalAggregation:
    events = prepare_dashboard_events(frame).dropna(
        subset=["origin_time_utc"]
    ).copy()
    if events.empty:
        return TemporalAggregation(
            pd.DataFrame({"period": [], "events": []}),
            "period",
            "Eventos por período",
            "Período",
        )

    span = calendar_span_years(events["origin_time_utc"])
    events["year"] = extract_years(events["origin_time_utc"])
    events = events.dropna(subset=["year"])
    events["year"] = events["year"].astype(int)

    if span > 15:
        counts = (
            events.groupby("year", as_index=False)
            .size()
            .rename(columns={"size": "events"})
            .sort_values("year")
        )
        return TemporalAggregation(
            counts,
            "year",
            "Registos do catálogo por ano",
            "Ano",
        )

    events["period"] = events["origin_time_utc"].map(_format_month)
    counts = (
        events.groupby("period", as_index=False)
        .size()
        .rename(columns={"size": "events"})
        .sort_values("period")
    )
    return TemporalAggregation(
        counts,
        "period",
        "Registos do catálogo por mês",
        "Mês",
    )


def safe_fractional_date(values: pd.Series, fraction: float):
    dates = values.dropna().sort_values()
    if dates.empty:
        raise ValueError("Não existem datas válidas.")
    fraction = float(np.clip(fraction, 0.0, 1.0))
    index = min(len(dates) - 1, int(round((len(dates) - 1) * fraction)))
    return dates.iloc[index]



SOURCE_DISPLAY_NAMES = {
    "IPMA": "IPMA",
    "AHEAD": "AHEAD / EPICA",
    "ISC": "ISC",
    "IPMA_HISTORICAL": "IPMA histórico",
    "DEMO": "Demonstração",
}


def format_date_pt(value: object, include_time: bool = False) -> str:
    if value is None or value is pd.NaT:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        pass

    formatter = getattr(value, "strftime", None)
    if callable(formatter):
        try:
            return formatter(
                "%d/%m/%Y %H:%M UTC"
                if include_time
                else "%d/%m/%Y"
            )
        except (ValueError, OverflowError):
            pass

    text = str(value)
    parsed = pd.to_datetime(text, utc=True, errors="coerce")
    if not pd.isna(parsed):
        return parsed.strftime(
            "%d/%m/%Y %H:%M UTC"
            if include_time
            else "%d/%m/%Y"
        )
    return text


def format_percentage(value: object, decimals: int = 1) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "—"
    return f"{float(numeric) * 100:.{decimals}f}%"


def format_number(value: object, decimals: int = 1, suffix: str = "") -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "—"
    return f"{float(numeric):.{decimals}f}{suffix}"


def format_boolean_pt(value: object) -> str:
    if value is None or value is pd.NA:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        pass
    return "Sim" if bool(value) else "Não"


def catalogue_consolidation_summary(frame: pd.DataFrame) -> dict[str, float | int]:
    events = frame.copy()
    raw_records = int(len(events))
    preferred_mask = (
        events.get(
            "is_preferred_record",
            pd.Series(True, index=events.index),
        )
        .fillna(True)
        .astype(bool)
    )
    consolidated_events = int(preferred_mask.sum())
    redundant_records = max(0, raw_records - consolidated_events)
    duplicate_groups = int(
        events.get(
            "duplicate_group_id",
            pd.Series(dtype="string"),
        )
        .dropna()
        .astype(str)
        .nunique()
    )
    consolidation_rate = (
        redundant_records / raw_records
        if raw_records
        else 0.0
    )
    return {
        "raw_records": raw_records,
        "consolidated_events": consolidated_events,
        "redundant_records": redundant_records,
        "duplicate_groups": duplicate_groups,
        "consolidation_rate": consolidation_rate,
    }


def build_source_pipeline_status(frame: pd.DataFrame) -> pd.DataFrame:
    events = frame.copy()
    if "source" not in events.columns:
        events["source"] = ""

    preferred_mask = (
        events.get(
            "is_preferred_record",
            pd.Series(True, index=events.index),
        )
        .fillna(True)
        .astype(bool)
    )

    rows: list[dict[str, object]] = []
    source_directories = {
        "IPMA": PATHS.bronze / "ipma",
        "AHEAD": PATHS.bronze / "ahead",
        "ISC": PATHS.bronze / "isc",
    }

    for source, folder in source_directories.items():
        source_events = events[
            events["source"].astype(str) == source
        ].copy()
        preferred_source = source_events.loc[
            preferred_mask.reindex(
                source_events.index,
                fill_value=True,
            )
        ]

        snapshots = (
            list(folder.rglob("*.json"))
            if folder.exists()
            else []
        )
        latest_snapshot = (
            max(snapshots, key=lambda path: path.stat().st_mtime)
            if snapshots
            else None
        )

        raw_count = int(len(source_events))
        preferred_count = int(len(preferred_source))

        if preferred_count > 0:
            status = "Integrada"
            action = "Nenhuma"
        elif raw_count > 0:
            status = "Presente no Silver"
            action = "Rever preferência/deduplicação"
        elif snapshots:
            status = "Recolhida"
            action = "Reconstruir Silver e Gold"
        else:
            status = "Não recolhida"
            action = "Executar ingestão"

        last_event = (
            source_events["origin_time_utc"].max()
            if not source_events.empty
            else pd.NaT
        )

        rows.append(
            {
                "Fonte": SOURCE_DISPLAY_NAMES.get(source, source),
                "Estado": status,
                "Snapshots Bronze": len(snapshots),
                "Registos no Silver": raw_count,
                "Eventos consolidados": preferred_count,
                "Último evento": format_date_pt(
                    last_event,
                    include_time=True,
                ),
                "Última recolha": (
                    pd.Timestamp(
                        latest_snapshot.stat().st_mtime,
                        unit="s",
                        tz="UTC",
                    ).strftime("%d/%m/%Y %H:%M UTC")
                    if latest_snapshot
                    else "—"
                ),
                "Próxima ação": action,
            }
        )

    return pd.DataFrame(rows)

@dataclass(frozen=True)
class ActivityAssessment:
    label: str
    level: str
    interpretation: str
    evidence: str
    robust_elevation: bool
    inconclusive: bool


def assess_activity_state(
    percentile: float | None,
    ci_lower: float | None,
    ci_upper: float | None,
    effective_sample_size: float | None,
    elevation_threshold: float = 0.80,
    exceptional_threshold: float = 0.95,
    minimum_effective_sample: float = 5.0,
) -> ActivityAssessment:
    values = [percentile, ci_lower, ci_upper, effective_sample_size]
    if any(value is None or pd.isna(value) for value in values):
        return ActivityAssessment(
            "Inconclusivo — referência insuficiente",
            "watch",
            "A referência comparável ainda não permite classificar o estado com robustez.",
            "Faltam estimativas de incerteza ou tamanho efetivo da amostra.",
            False,
            True,
        )

    p = float(percentile)
    lower = float(ci_lower)
    upper = float(ci_upper)
    effective = float(effective_sample_size)
    if effective < minimum_effective_sample:
        return ActivityAssessment(
            "Inconclusivo — amostra efetiva reduzida",
            "watch",
            "A estimativa central existe, mas a dependência temporal deixa poucas observações independentes.",
            f"Amostra efetiva aproximada: {effective:.1f}.",
            False,
            True,
        )
    if lower >= exceptional_threshold:
        return ActivityAssessment(
            "Elevação excecional robusta",
            "high",
            "Todo o intervalo de incerteza permanece numa zona excecionalmente elevada.",
            f"Percentil {p:.0%}; IC 95% {lower:.0%}–{upper:.0%}.",
            True,
            False,
        )
    if lower >= elevation_threshold:
        return ActivityAssessment(
            "Atividade elevada com suporte estatístico",
            "high",
            "O limite inferior do intervalo permanece acima da linha de elevação definida.",
            f"Percentil {p:.0%}; IC 95% {lower:.0%}–{upper:.0%}.",
            True,
            False,
        )
    if upper < elevation_threshold:
        return ActivityAssessment(
            "Sem evidência robusta de elevação",
            "normal",
            "O intervalo de incerteza permanece abaixo do limiar de atividade elevada.",
            f"Percentil {p:.0%}; IC 95% {lower:.0%}–{upper:.0%}.",
            False,
            False,
        )
    return ActivityAssessment(
        "Inconclusivo — intervalo atravessa o limiar",
        "watch",
        "A estimativa central não permite distinguir claramente linha de base e elevação.",
        f"Percentil {p:.0%}; IC 95% {lower:.0%}–{upper:.0%}.",
        False,
        True,
    )


def activity_label(percentile: float | None) -> tuple[str, str]:
    if percentile is None or pd.isna(percentile):
        return "Sem referência", "neutral"
    value = float(percentile)
    if value >= 0.95:
        return "Atividade elevada", "high"
    if value >= 0.75:
        return "Em observação", "watch"
    return "Dentro da linha de base", "normal"


def prepare_map_data(frame: pd.DataFrame, minimum_magnitude: float) -> pd.DataFrame:
    events = prepare_dashboard_events(frame)
    events = events[
        pd.to_numeric(events["magnitude_comparable"], errors="coerce")
        >= float(minimum_magnitude)
    ].copy()
    events = events.dropna(
        subset=["latitude", "longitude", "magnitude_comparable"]
    )

    events["marker_size"] = np.clip(
        (events["magnitude_comparable"].to_numpy(dtype=float) ** 2.15) * 2.5,
        7.0,
        46.0,
    )
    events["origin_time_display"] = events["origin_time_utc"].map(
        _format_datetime
    )
    events["location_display"] = (
        events["location_text"]
        .astype("string")
        .replace("", pd.NA)
        .fillna("Localização não indicada")
    )
    source_values = events.get(
        "source",
        pd.Series("", index=events.index, dtype="string"),
    )
    events["source_display"] = (
        source_values.astype("string")
        .replace("", pd.NA)
        .fillna("Fonte não indicada")
    )
    events["depth_display"] = events["depth_km"].map(
        lambda value: "—" if pd.isna(value) else f"{float(value):.1f} km"
    )
    events["magnitude_display"] = events["magnitude_comparable"].map(
        lambda value: f"{float(value):.1f}"
    )
    events["coordinates_display"] = [
        f"{lat:.3f}, {lon:.3f}"
        for lat, lon in zip(events["latitude"], events["longitude"])
    ]
    events["hover_text"] = (
        "<b>" + events["location_display"].astype(str) + "</b>"
        + "<br>Data: " + events["origin_time_display"].astype(str)
        + "<br>Magnitude: " + events["magnitude_display"].astype(str)
        + "<br>Profundidade: " + events["depth_display"].astype(str)
        + "<br>Fonte: " + events["source_display"].astype(str)
        + "<br>Coordenadas: " + events["coordinates_display"].astype(str)
    )
    return events[
        [
            "latitude",
            "longitude",
            "magnitude_comparable",
            "marker_size",
            "hover_text",
        ]
    ].copy()


def _robust_density_grid(data: pd.DataFrame, bins: int = 70) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()
    latitude_edges = np.linspace(data["latitude"].min(), data["latitude"].max(), bins + 1)
    longitude_edges = np.linspace(data["longitude"].min(), data["longitude"].max(), bins + 1)
    latitude_bin = np.clip(np.digitize(data["latitude"], latitude_edges) - 1, 0, bins - 1)
    longitude_bin = np.clip(np.digitize(data["longitude"], longitude_edges) - 1, 0, bins - 1)
    working = data.copy()
    working["latitude_bin"] = latitude_bin
    working["longitude_bin"] = longitude_bin
    grid = (
        working.groupby(["latitude_bin", "longitude_bin"], as_index=False)
        .agg(
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
            events=("latitude", "count"),
            maximum_magnitude=("magnitude_comparable", "max"),
        )
    )
    grid["log_density"] = np.log1p(grid["events"].astype(float))
    cap = float(grid["log_density"].quantile(0.99)) if len(grid) > 1 else float(grid["log_density"].max())
    grid["display_density"] = grid["log_density"].clip(upper=max(cap, 1e-6))
    grid["marker_size"] = np.clip(7.0 + np.sqrt(grid["events"]) * 2.8, 8.0, 34.0)
    grid["hover_text"] = (
        "<b>Célula de densidade</b><br>Eventos: "
        + grid["events"].astype(str)
        + "<br>M máxima: "
        + grid["maximum_magnitude"].map(lambda value: f"{float(value):.1f}")
    )
    return grid



def estimate_map_zoom(data: pd.DataFrame, fallback: float = 4.2) -> float:
    if data.empty:
        return fallback
    lat_span = max(float(data["latitude"].max() - data["latitude"].min()), 0.05)
    lon_span = max(float(data["longitude"].max() - data["longitude"].min()), 0.05)
    span = max(lat_span, lon_span * 0.75)
    return float(np.clip(7.8 - np.log2(span + 0.15), 3.2, 8.5))


def density_grid_resolution_km(data: pd.DataFrame, bins: int = 70) -> float:
    if data.empty:
        return np.nan
    lat_span_km = abs(float(data["latitude"].max() - data["latitude"].min())) * 111.0
    mean_lat = np.deg2rad(float(data["latitude"].mean()))
    lon_span_km = abs(float(data["longitude"].max() - data["longitude"].min())) * 111.0 * max(np.cos(mean_lat), 0.2)
    return float(max(lat_span_km, lon_span_km) / max(bins, 1))


def build_event_map_figure(
    frame: pd.DataFrame,
    minimum_magnitude: float,
    zoom: float | None = None,
    height: int = 500,
    display_mode: str = "cluster",
    maximum_individual_points: int = 5000,
) -> go.Figure:
    data = prepare_map_data(frame, minimum_magnitude)
    figure = go.Figure()

    if data.empty:
        figure.add_annotation(
            text="Sem eventos para o filtro selecionado",
            x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
            font={"size": 14, "color": "#607385"},
        )
        center = {"lat": 38.0, "lon": -9.5}
    else:
        center = {
            "lat": float(data["latitude"].mean()),
            "lon": float(data["longitude"].mean()),
        }
        common_colorscale = [
            [0.00, "#9BE7C4"],
            [0.35, "#41B8D5"],
            [0.70, "#176B87"],
            [1.00, "#071A2D"],
        ]

        if display_mode == "density":
            grid = _robust_density_grid(data)
            figure.add_trace(
                go.Densitymap(
                    lat=grid["latitude"],
                    lon=grid["longitude"],
                    z=grid["display_density"],
                    radius=10,
                    colorscale=common_colorscale,
                    showscale=True,
                    zmin=0.0,
                    zmax=float(grid["display_density"].max()),
                    colorbar={
                        "title": "log(1+eventos)",
                        "thickness": 12,
                        "len": 0.72,
                        "outlinewidth": 0,
                    },
                    hoverinfo="skip",
                    name="Densidade robusta",
                )
            )
        else:
            plot_data = data
            if display_mode == "points" and len(plot_data) > maximum_individual_points:
                strongest = plot_data.nlargest(
                    min(750, maximum_individual_points),
                    "magnitude_comparable",
                )
                remaining = plot_data.drop(index=strongest.index)
                sample_size = max(0, maximum_individual_points - len(strongest))
                sampled = remaining.sample(
                    n=min(sample_size, len(remaining)),
                    random_state=42,
                )
                plot_data = pd.concat([strongest, sampled], ignore_index=True)

            marker = {
                "color": plot_data["magnitude_comparable"].to_numpy(dtype=float),
                "colorscale": common_colorscale,
                "showscale": True,
                "colorbar": {
                    "title": "Magnitude",
                    "thickness": 12,
                    "len": 0.72,
                    "outlinewidth": 0,
                },
                "opacity": 0.82,
                "size": (
                    np.clip(plot_data["marker_size"].to_numpy(dtype=float), 6.0, 28.0)
                    if display_mode == "cluster"
                    else plot_data["marker_size"].to_numpy(dtype=float)
                ),
            }
            kwargs: dict[str, object] = {}
            if display_mode == "cluster":
                kwargs["cluster"] = {
                    "enabled": True,
                    "maxzoom": 8,
                    "step": 40,
                    "size": 28,
                    "opacity": 0.78,
                }
            figure.add_trace(
                go.Scattermap(
                    lat=plot_data["latitude"].to_numpy(dtype=float),
                    lon=plot_data["longitude"].to_numpy(dtype=float),
                    mode="markers",
                    text=plot_data["hover_text"].astype(str).tolist(),
                    hovertemplate="%{text}<extra></extra>",
                    marker=marker,
                    name="Eventos",
                    **kwargs,
                )
            )

    resolved_zoom = estimate_map_zoom(data) if zoom is None else float(zoom)
    figure.update_layout(
        map={"style": "carto-positron", "center": center, "zoom": resolved_zoom},
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font={"family": "Inter, Segoe UI, sans-serif", "color": "#17324A"},
        hoverlabel={
            "bgcolor": "#071A2D",
            "font": {"color": "white", "size": 12},
            "bordercolor": "#41B8D5",
        },
    )
    return figure
