from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np
import pandas as pd

from src.common import haversine_km
from src.schema import ensure_event_schema

SOURCE_PRIORITY = {
    "IPMA": 5,
    "IPMA_HISTORICAL": 4,
    "ISC": 4,
    "AHEAD": 3,
    "DEMO": 1,
}


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left


def _is_duplicate(
    left: pd.Series,
    right: pd.Series,
    time_seconds: float,
    distance_km: float,
    magnitude_delta: float,
) -> bool:
    time_diff = abs((left["origin_time_utc"] - right["origin_time_utc"]).total_seconds())
    if time_diff > time_seconds:
        return False
    distance = float(
        haversine_km(
            left["latitude"],
            left["longitude"],
            right["latitude"],
            right["longitude"],
        )
    )
    if distance > distance_km:
        return False
    left_mag, right_mag = left["magnitude_value"], right["magnitude_value"]
    if pd.notna(left_mag) and pd.notna(right_mag):
        return abs(float(left_mag) - float(right_mag)) <= magnitude_delta
    return True


def _preference_score(row: pd.Series) -> tuple[float, float, float, float]:
    source = SOURCE_PRIORITY.get(str(row["source"]), 0)
    status = {"reviewed": 3, "historical": 2, "preliminary": 1, "demo": 0}.get(
        str(row["record_status"]), 0
    )
    completeness = sum(
        pd.notna(row[column])
        for column in ["depth_km", "magnitude_value", "magnitude_type", "location_text"]
    )
    quality = float(row["quality_score"]) if pd.notna(row["quality_score"]) else 0.0
    return source, status, completeness, quality


def deduplicate_events(
    frame: pd.DataFrame,
    time_seconds: float = 90,
    distance_km: float = 35,
    magnitude_delta: float = 0.6,
) -> pd.DataFrame:
    events = ensure_event_schema(frame).dropna(
        subset=["origin_time_utc", "latitude", "longitude"]
    ).copy()
    events = events.sort_values("origin_time_utc").reset_index(drop=True)
    if events.empty:
        return events

    union = UnionFind(len(events))
    times = events["origin_time_utc"].tolist()

    for i in range(len(events)):
        j = i + 1
        while j < len(events):
            if (times[j] - times[i]).total_seconds() > time_seconds:
                break
            if _is_duplicate(events.iloc[i], events.iloc[j], time_seconds, distance_km, magnitude_delta):
                union.union(i, j)
            j += 1

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(events)):
        groups[union.find(index)].append(index)

    events["duplicate_group_id"] = pd.NA
    events["is_preferred_record"] = True
    for indices in groups.values():
        if len(indices) == 1:
            continue
        fingerprint = "|".join(sorted(str(events.iloc[i]["event_id_memoria"]) for i in indices))
        group_id = "DUP-" + hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:12].upper()
        ranked = sorted(indices, key=lambda i: _preference_score(events.iloc[i]), reverse=True)
        preferred = ranked[0]
        for index in indices:
            events.at[index, "duplicate_group_id"] = group_id
            events.at[index, "is_preferred_record"] = index == preferred
    return ensure_event_schema(events)


def preferred_events(frame: pd.DataFrame) -> pd.DataFrame:
    events = ensure_event_schema(frame)
    mask = events["is_preferred_record"].fillna(True)
    return events.loc[mask].copy().reset_index(drop=True)
