from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from src.schema import ensure_event_schema

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class DeclusterParameters:
    minimum_mainshock_magnitude: float = 3.0
    minimum_radius_km: float = 12.0
    maximum_radius_km: float = 180.0
    minimum_window_days: float = 1.0
    maximum_window_days: float = 365.0


def spatial_window_km(magnitude: float, parameters: DeclusterParameters) -> float:
    radius = 10.0 ** (0.50 * float(magnitude) - 0.75)
    return float(np.clip(radius, parameters.minimum_radius_km, parameters.maximum_radius_km))


def temporal_window_days(magnitude: float, parameters: DeclusterParameters) -> float:
    days = 10.0 ** (0.80 * float(magnitude) - 1.20)
    return float(np.clip(days, parameters.minimum_window_days, parameters.maximum_window_days))


def _exclusion_reason(row: pd.Series) -> str:
    missing: list[str] = []
    if pd.isna(row.get("origin_time_utc")):
        missing.append("data")
    if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
        missing.append("coordenadas")
    if pd.isna(row.get("magnitude_comparable")):
        missing.append("magnitude")
    return "missing_" + "_".join(missing) if missing else "eligible"


def annotate_declustering(
    frame: pd.DataFrame,
    parameters: DeclusterParameters | None = None,
) -> pd.DataFrame:
    """Annotate an auditable pilot mainshock/associated-event separation.

    Every record receives an explicit role. Preferred records missing date,
    coordinates or comparable magnitude are marked ``ineligible`` rather than
    silently disappearing from the reconciliation. Redundant source records are
    kept outside the scientific declustering population.
    """
    parameters = parameters or DeclusterParameters()
    result = ensure_event_schema(frame)
    preferred_mask = result["is_preferred_record"].fillna(True).astype(bool)

    result["cluster_id"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result["cluster_role"] = pd.Series("unclassified", index=result.index, dtype="string")
    result["is_background_event"] = pd.Series(False, index=result.index, dtype="boolean")
    result["declustering_method"] = pd.Series(
        "pilot_adaptive_space_time_v2", index=result.index, dtype="string"
    )
    result["declustering_eligible"] = pd.Series(False, index=result.index, dtype="boolean")
    result["declustering_exclusion_reason"] = pd.Series(pd.NA, index=result.index, dtype="string")

    redundant_mask = ~preferred_mask
    result.loc[redundant_mask, "cluster_role"] = "redundant_record"
    result.loc[redundant_mask, "declustering_exclusion_reason"] = "redundant_source_record"

    preferred = result.loc[preferred_mask].copy()
    reasons = preferred.apply(_exclusion_reason, axis=1)
    eligible_index = reasons[reasons.eq("eligible")].index
    ineligible_index = reasons[~reasons.eq("eligible")].index

    result.loc[eligible_index, "declustering_eligible"] = True
    result.loc[eligible_index, "declustering_exclusion_reason"] = "eligible"
    result.loc[ineligible_index, "cluster_role"] = "ineligible"
    result.loc[ineligible_index, "declustering_exclusion_reason"] = reasons.loc[ineligible_index]

    working = result.loc[eligible_index].copy()
    if working.empty:
        return ensure_event_schema(result)

    working["_time"] = pd.to_datetime(working["origin_time_utc"], utc=True, errors="coerce")
    working["_magnitude"] = pd.to_numeric(working["magnitude_comparable"], errors="coerce")
    coordinates = np.deg2rad(working[["latitude", "longitude"]].to_numpy(dtype=float))
    tree = BallTree(coordinates, metric="haversine")
    times_ns = working["_time"].astype("int64").to_numpy()
    magnitudes = working["_magnitude"].to_numpy(dtype=float)
    original_indices = working.index.to_numpy()

    assigned_cluster = np.full(len(working), "", dtype=object)
    roles = np.full(len(working), "background", dtype=object)
    order = np.lexsort((times_ns, -magnitudes))
    cluster_counter = 0

    for position in order:
        magnitude = magnitudes[position]
        if not np.isfinite(magnitude) or magnitude < parameters.minimum_mainshock_magnitude:
            continue
        if assigned_cluster[position]:
            continue
        radius_km = spatial_window_km(magnitude, parameters)
        window_days = temporal_window_days(magnitude, parameters)
        neighbours = tree.query_radius(
            coordinates[position : position + 1],
            r=radius_km / EARTH_RADIUS_KM,
            return_distance=False,
        )[0]
        if len(neighbours) <= 1:
            continue
        delta_days = (times_ns[neighbours] - times_ns[position]) / 86_400_000_000_000.0
        eligible = neighbours[
            (delta_days > 0)
            & (delta_days <= window_days)
            & (magnitudes[neighbours] <= magnitude + 1e-9)
            & (assigned_cluster[neighbours] == "")
        ]
        if len(eligible) == 0:
            continue
        cluster_counter += 1
        cluster_id = f"SEQ-{cluster_counter:06d}"
        assigned_cluster[position] = cluster_id
        roles[position] = "mainshock"
        assigned_cluster[eligible] = cluster_id
        roles[eligible] = "associated_event"

    for local_position, original_index in enumerate(original_indices):
        cluster_id = assigned_cluster[local_position]
        role = roles[local_position]
        result.at[original_index, "cluster_id"] = cluster_id if cluster_id else pd.NA
        result.at[original_index, "cluster_role"] = role
        result.at[original_index, "is_background_event"] = role in {"background", "mainshock"}

    return ensure_event_schema(result)


def select_catalogue_mode(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    events = ensure_event_schema(frame)
    if mode == "declustered":
        mask = events["is_background_event"].fillna(False)
        return events.loc[mask].copy().reset_index(drop=True)
    return events.copy().reset_index(drop=True)


def declustering_summary(frame: pd.DataFrame) -> dict[str, float | int | str]:
    events = ensure_event_schema(frame)
    preferred = events[events["is_preferred_record"].fillna(True)].copy()
    total = int(len(preferred))
    eligible = int(preferred["declustering_eligible"].fillna(False).sum())
    background = int(preferred["is_background_event"].fillna(False).sum())
    associated = int(preferred["cluster_role"].astype(str).eq("associated_event").sum())
    mainshocks = int(preferred["cluster_role"].astype(str).eq("mainshock").sum())
    ineligible = int(preferred["cluster_role"].astype(str).eq("ineligible").sum())
    unclassified = int(preferred["cluster_role"].astype(str).eq("unclassified").sum())
    sequences = int(preferred["cluster_id"].dropna().nunique())
    reconciled = background + associated + ineligible + unclassified
    return {
        "preferred_events": total,
        "eligible_events": eligible,
        "background_events": background,
        "associated_events": associated,
        "mainshocks": mainshocks,
        "ineligible_events": ineligible,
        "unclassified_events": unclassified,
        "reconciled_events": reconciled,
        "reconciliation_gap": total - reconciled,
        "sequences": sequences,
        "retained_fraction": background / total if total else 0.0,
        "retained_fraction_eligible": background / eligible if eligible else 0.0,
        "method": "pilot_adaptive_space_time_v2",
    }


def declustering_exclusion_summary(frame: pd.DataFrame) -> pd.DataFrame:
    events = ensure_event_schema(frame)
    preferred = events[events["is_preferred_record"].fillna(True)].copy()
    excluded = preferred[~preferred["declustering_eligible"].fillna(False)].copy()
    if excluded.empty:
        return pd.DataFrame(columns=["Motivo", "Registos"])
    return (
        excluded["declustering_exclusion_reason"]
        .fillna("unknown")
        .astype(str)
        .value_counts()
        .rename_axis("Motivo")
        .reset_index(name="Registos")
    )
