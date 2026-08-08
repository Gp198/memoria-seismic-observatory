from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape


def load_faults_geojson(path: str | Path) -> list[dict[str, object]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    faults = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue
        faults.append({
            "name": (feature.get("properties") or {}).get("name", "Fault"),
            "geometry": shape(geometry),
            "properties": feature.get("properties") or {},
        })
    return faults


def nearest_fault_summary(events: pd.DataFrame, faults: list[dict[str, object]]) -> pd.DataFrame:
    if not faults or events.empty:
        return pd.DataFrame()
    rows = []
    for _, event in events.dropna(subset=["latitude", "longitude"]).iterrows():
        point = Point(float(event["longitude"]), float(event["latitude"]))
        candidates = []
        for fault in faults:
            # Degree distance converted approximately to km; explicitly approximate.
            distance_km = float(point.distance(fault["geometry"]) * 111.2)
            candidates.append((distance_km, str(fault["name"])))
        distance, name = min(candidates)
        rows.append({
            "event_id_memoria": event.get("event_id_memoria"),
            "nearest_fault": name,
            "fault_distance_km_approx": distance,
        })
    return pd.DataFrame(rows)
