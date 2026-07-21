from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.backtesting.replay import ReplayResult
from src.config import PATHS
from src.quality.completeness import estimate_magnitude_completeness
from src.quality.deduplication import preferred_events


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render Markdown without making report generation depend on tabulate."""
    clean = frame.copy()
    clean.columns = [str(column) for column in clean.columns]
    for column in clean.columns:
        clean[column] = clean[column].map(
            lambda value: "" if pd.isna(value) else str(value).replace("|", r"\|")
        )
    header = "| " + " | ".join(clean.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(clean.columns)) + " |"
    rows = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in clean.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows])



def similarity_summary(result) -> str:
    target = result.target
    neighbours = result.neighbours
    if neighbours.empty:
        return "Não foram encontrados estados históricos comparáveis."
    best = neighbours.iloc[0]
    percentile = target.get("comparable_percentile_event_rate")
    percentile_text = (
        f"{float(percentile):.0%}"
        if pd.notna(percentile)
        else "indisponível"
    )
    epoch_label = target.get(
        "comparison_epoch_label", result.target_epoch
    )
    threshold = target.get("comparison_magnitude_threshold")
    threshold_text = (
        f"M≥{float(threshold):.1f}"
        if pd.notna(threshold)
        else "limiar indisponível"
    )
    return (
        f"O estado termina em {pd.to_datetime(target['window_end']).date()} "
        f"e situa-se no percentil comparável {percentile_text} da época "
        f"«{epoch_label}», usando {threshold_text}. A família temporal mais "
        f"semelhante tem como representante a janela terminada em "
        f"{pd.to_datetime(best['window_end']).date()}, com semelhança "
        f"{float(best['similarity']):.1%} e compatibilidade "
        f"{float(best['comparability_score']):.1%}. A semelhança descreve "
        "proximidade estatística, não causalidade nem previsão."
    )


def replay_summary(result: ReplayResult) -> str:
    observed = "ocorreu" if result.observed_outcome else "não ocorreu"
    baseline = result.baseline
    return (
        f"No replay com corte em {result.cutoff.date()}, a frequência "
        f"ponderada entre famílias análogas foi "
        f"{result.analogue_probability:.1%}; "
        f"a frequência empírica foi "
        f"{result.historical_rate_probability:.1%}; e o Poisson, calculado "
        f"sobre a mesma exposição, foi {result.poisson_probability:.1%}. "
        f"As linhas de base usam a época «{baseline.epoch_label}», "
        f"{baseline.threshold_event_count} eventos M≥"
        f"{result.threshold_magnitude:.1f} e "
        f"{baseline.exposure_days / 365.25:.1f} anos de exposição. "
        f"No horizonte observado, {observed} um evento "
        f"M≥{result.threshold_magnitude:.1f}. O score das famílias não é uma "
        "probabilidade calibrada e não constitui um alerta."
    )


def generate_markdown_report(events: pd.DataFrame, fingerprints: pd.DataFrame) -> Path:
    PATHS.reports.mkdir(parents=True, exist_ok=True)
    clean = preferred_events(events)
    source_counts = clean["source"].value_counts(dropna=False)
    domain_counts = clean["tectonic_domain"].value_counts(dropna=False)
    completeness_rows = []
    for domain, group in clean.groupby("tectonic_domain"):
        estimate = estimate_magnitude_completeness(group["magnitude_comparable"])
        completeness_rows.append(
            f"| {domain} | {estimate.event_count} | "
            f"{estimate.mc if estimate.mc is not None else 'insuficiente'} |"
        )

    grouping = ["tectonic_domain", "window_days"]
    if "catalogue_mode" in fingerprints.columns:
        grouping.insert(0, "catalogue_mode")
    latest = fingerprints.sort_values("window_end").groupby(
        grouping, as_index=False
    ).tail(1)

    lines = [
        "# MEMÓRIA — Relatório automático",
        "",
        "## Estado do catálogo",
        "",
        f"- Eventos preferenciais: **{len(clean):,}**",
        f"- Período: **{clean['origin_time_utc'].min()}** a **{clean['origin_time_utc'].max()}**",
        f"- Fontes: **{', '.join(source_counts.index.astype(str))}**",
        "",
        "### Eventos por fonte",
        "",
        "| Fonte | Eventos |",
        "|---|---:|",
    ]
    lines.extend(f"| {source} | {count} |" for source, count in source_counts.items())
    lines.extend(
        [
            "",
            "### Eventos por domínio",
            "",
            "| Domínio | Eventos |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| {domain} | {count} |" for domain, count in domain_counts.items())
    lines.extend(
        [
            "",
            "### Magnitude de completude",
            "",
            "| Domínio | Amostra | Mc estimada |",
            "|---|---:|---:|",
            *completeness_rows,
            "",
            "## Fingerprints mais recentes",
            "",
        ]
    )
    if latest.empty:
        lines.append("Sem fingerprints disponíveis.")
    else:
        lines.append(
            _markdown_table(
                latest[
                    [
                        *(
                            ["catalogue_mode"]
                            if "catalogue_mode" in latest.columns
                            else []
                        ),
                        "tectonic_domain",
                        "window_days",
                        "window_end",
                        "event_count",
                        "comparable_event_count",
                        "comparison_epoch_label",
                        "comparison_magnitude_threshold",
                        "maximum_magnitude",
                        "comparable_percentile_event_rate",
                        "comparable_reference_windows",
                        "comparable_effective_sample_size",
                        "comparable_percentile_ci_lower",
                        "comparable_percentile_ci_upper",
                    ]
                ]
            )
        )
    lines.extend(
        [
            "",
            "## Limite de comunicação",
            "",
            "Este relatório descreve estados estatísticos e qualidade de dados. "
            "Não prevê data, local ou magnitude de um futuro sismo e não substitui informação oficial.",
        ]
    )
    path = PATHS.reports / "latest_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
