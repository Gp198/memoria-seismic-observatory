from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import PATHS
from src.schema import ensure_event_schema


@dataclass(frozen=True)
class MagnitudeRule:
    source_type: str
    slope: float
    intercept: float
    uncertainty: float
    method: str
    equation: str
    status: str


_MW_TYPES = {
    "MW",
    "MWW",
    "MWC",
    "MWR",
    "MWB",
    "MWP",
}


def normalise_magnitude_type(value: object) -> str:
    if value is None or pd.isna(value):
        return "UNKNOWN"
    text = str(value).strip().upper().replace(" ", "")
    return text or "UNKNOWN"


def default_policy_path() -> Path:
    return PATHS.root / "config" / "magnitude_conversion_policy.json"


def load_conversion_policy(path: str | Path | None = None) -> dict[str, MagnitudeRule]:
    policy_path = Path(path) if path is not None else default_policy_path()
    if not policy_path.exists():
        return {}

    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    rules: dict[str, MagnitudeRule] = {}
    for raw_type, raw_rule in payload.get("rules", {}).items():
        magnitude_type = normalise_magnitude_type(raw_type)
        rules[magnitude_type] = MagnitudeRule(
            source_type=magnitude_type,
            slope=float(raw_rule["slope"]),
            intercept=float(raw_rule["intercept"]),
            uncertainty=float(raw_rule.get("uncertainty", 0.30)),
            method=str(raw_rule.get("method", "affine_policy")),
            equation=str(
                raw_rule.get(
                    "equation",
                    f"Mcomp={float(raw_rule['slope']):.4g}×M+"
                    f"{float(raw_rule['intercept']):.4g}",
                )
            ),
            status=str(raw_rule.get("status", "review_required")),
        )
    return rules


def _maximum_uncertainty(current: object, floor: float) -> float:
    value = pd.to_numeric(pd.Series([current]), errors="coerce").iloc[0]
    if pd.isna(value):
        return float(floor)
    return float(max(float(value), floor))


def homogenize_magnitudes(
    frame: pd.DataFrame,
    policy_path: str | Path | None = None,
) -> pd.DataFrame:
    """Create an auditable operational comparison magnitude.

    Only moment-magnitude variants are treated as reviewed identity mappings by
    default. Other scales retain their numeric value as a transparent fallback
    until a seismologist-reviewed conversion policy is supplied. The fallback
    is deliberately marked as unvalidated and receives wider uncertainty.
    """
    result = ensure_event_schema(frame)
    rules = load_conversion_policy(policy_path)

    result["magnitude_original_value"] = pd.to_numeric(
        result["magnitude_original_value"].fillna(result["magnitude_value"]),
        errors="coerce",
    ).astype("Float64")
    result["magnitude_original_type"] = (
        result["magnitude_original_type"]
        .fillna(result["magnitude_type"])
        .astype("string")
    )

    comparable: list[float | pd.NA] = []
    methods: list[str] = []
    equations: list[str] = []
    uncertainties: list[float | pd.NA] = []
    statuses: list[str] = []

    for _, row in result.iterrows():
        original_value = row["magnitude_original_value"]
        original_type = normalise_magnitude_type(
            row["magnitude_original_type"]
        )
        original_uncertainty = row.get("magnitude_uncertainty")

        if pd.isna(original_value):
            comparable.append(pd.NA)
            methods.append("missing_magnitude")
            equations.append("—")
            uncertainties.append(pd.NA)
            statuses.append("missing")
            continue

        value = float(original_value)
        if original_type in _MW_TYPES:
            comparable.append(value)
            methods.append("moment_magnitude_identity")
            equations.append("Mcomp = Mw")
            uncertainties.append(
                _maximum_uncertainty(original_uncertainty, 0.10)
            )
            statuses.append("reviewed_identity")
            continue

        rule = rules.get(original_type)
        if rule is not None:
            converted = rule.slope * value + rule.intercept
            comparable.append(float(converted))
            methods.append(rule.method)
            equations.append(rule.equation)
            uncertainties.append(
                _maximum_uncertainty(
                    original_uncertainty,
                    rule.uncertainty,
                )
            )
            statuses.append(rule.status)
            continue

        comparable.append(value)
        methods.append("identity_fallback_unvalidated")
        equations.append("Mcomp ≈ Moriginal (conversão não validada)")
        uncertainties.append(
            _maximum_uncertainty(
                original_uncertainty,
                0.50 if original_type == "UNKNOWN" else 0.35,
            )
        )
        statuses.append(
            "unknown_scale" if original_type == "UNKNOWN" else "review_required"
        )

    result["magnitude_comparable"] = pd.Series(
        comparable,
        index=result.index,
        dtype="Float64",
    )
    result["magnitude_homogenization_method"] = pd.Series(
        methods,
        index=result.index,
        dtype="string",
    )
    result["magnitude_conversion_equation"] = pd.Series(
        equations,
        index=result.index,
        dtype="string",
    )
    result["magnitude_conversion_uncertainty"] = pd.Series(
        uncertainties,
        index=result.index,
        dtype="Float64",
    )
    result["magnitude_homogenization_status"] = pd.Series(
        statuses,
        index=result.index,
        dtype="string",
    )
    return ensure_event_schema(result)


def magnitude_audit_summary(frame: pd.DataFrame) -> pd.DataFrame:
    events = ensure_event_schema(frame).copy()
    events["magnitude_original_type"] = (
        events["magnitude_original_type"]
        .fillna(events["magnitude_type"])
        .map(normalise_magnitude_type)
    )
    events["magnitude_homogenization_status"] = (
        events["magnitude_homogenization_status"]
        .fillna("not_processed")
        .astype(str)
    )
    events["magnitude_homogenization_method"] = (
        events["magnitude_homogenization_method"]
        .fillna("not_processed")
        .astype(str)
    )

    grouped = (
        events.groupby(
            [
                "magnitude_original_type",
                "magnitude_homogenization_status",
                "magnitude_homogenization_method",
            ],
            dropna=False,
        )
        .agg(
            Registos=("event_id_memoria", "count"),
            Incerteza_mediana=(
                "magnitude_conversion_uncertainty",
                "median",
            ),
            Primeira_data=("origin_time_utc", "min"),
            Última_data=("origin_time_utc", "max"),
        )
        .reset_index()
        .sort_values("Registos", ascending=False)
    )
    return grouped


VALIDATED_MAGNITUDE_STATUSES = {
    "reviewed_identity",
    "reviewed_conversion",
    "approved_conversion",
}


def validated_magnitude_mask(frame: pd.DataFrame) -> pd.Series:
    events = ensure_event_schema(frame)
    status = events["magnitude_homogenization_status"].fillna("").astype(str)
    comparable = pd.to_numeric(events["magnitude_comparable"], errors="coerce").notna()
    return status.isin(VALIDATED_MAGNITUDE_STATUSES) & comparable


def select_magnitude_policy(frame: pd.DataFrame, policy: str) -> pd.DataFrame:
    """Select the operational or reviewed-only magnitude population."""
    events = ensure_event_schema(frame)
    if policy == "validated":
        return events.loc[validated_magnitude_mask(events)].copy().reset_index(drop=True)
    return events.copy().reset_index(drop=True)


def magnitude_policy_summary(frame: pd.DataFrame) -> dict[str, float | int]:
    events = ensure_event_schema(frame)
    preferred = events[events["is_preferred_record"].fillna(True)].copy()
    total = int(len(preferred))
    with_magnitude = int(pd.to_numeric(preferred["magnitude_comparable"], errors="coerce").notna().sum())
    validated = int(validated_magnitude_mask(preferred).sum())
    fallback = int(
        preferred["magnitude_homogenization_status"]
        .fillna("")
        .astype(str)
        .isin(["review_required", "unknown_scale"])
        .sum()
    )
    missing = max(0, total - with_magnitude)
    return {
        "preferred_events": total,
        "events_with_magnitude": with_magnitude,
        "validated_events": validated,
        "fallback_events": fallback,
        "missing_events": missing,
        "validated_fraction_total": validated / total if total else 0.0,
        "validated_fraction_with_magnitude": validated / with_magnitude if with_magnitude else 0.0,
    }
