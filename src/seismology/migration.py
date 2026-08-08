from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.common import haversine_km


@dataclass(frozen=True)
class MigrationEstimate:
    distance_km: float | None
    bearing_degrees: float | None
    speed_km_per_month: float | None
    depth_trend_km_per_month: float | None
    centroid_start_lat: float | None
    centroid_start_lon: float | None
    centroid_end_lat: float | None
    centroid_end_lon: float | None
    event_count: int
    sufficient_data: bool


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = np.radians(lat1); phi2 = np.radians(lat2)
    dlambda = np.radians(lon2 - lon1)
    x = np.sin(dlambda) * np.cos(phi2)
    y = np.cos(phi1) * np.sin(phi2) - np.sin(phi1) * np.cos(phi2) * np.cos(dlambda)
    return float((np.degrees(np.arctan2(x, y)) + 360.0) % 360.0)


def estimate_migration(events: pd.DataFrame, minimum_events: int = 12) -> MigrationEstimate:
    frame = events.copy()
    frame["origin_time_utc"] = pd.to_datetime(frame["origin_time_utc"], utc=True, errors="coerce")
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame["depth_km"] = pd.to_numeric(frame.get("depth_km"), errors="coerce")
    frame = frame.dropna(subset=["origin_time_utc", "latitude", "longitude"]).sort_values("origin_time_utc")
    n = len(frame)
    if n < minimum_events:
        return MigrationEstimate(None, None, None, None, None, None, None, None, n, False)

    split = max(1, n // 3)
    first = frame.iloc[:split]
    last = frame.iloc[-split:]
    lat1, lon1 = float(first["latitude"].median()), float(first["longitude"].median())
    lat2, lon2 = float(last["latitude"].median()), float(last["longitude"].median())
    distance = float(haversine_km(np.array([lat1]), np.array([lon1]), lat2, lon2)[0])
    duration_days = max(1e-6, (last["origin_time_utc"].median() - first["origin_time_utc"].median()).total_seconds() / 86400.0)
    speed = distance / duration_days * 30.4375

    depth = frame.dropna(subset=["depth_km"])
    depth_trend = None
    if len(depth) >= minimum_events:
        x = (depth["origin_time_utc"] - depth["origin_time_utc"].min()).dt.total_seconds().to_numpy() / 86400.0
        if np.ptp(x) > 0:
            slope = np.polyfit(x, depth["depth_km"].to_numpy(dtype=float), 1)[0]
            depth_trend = float(slope * 30.4375)

    return MigrationEstimate(
        distance_km=distance,
        bearing_degrees=_bearing(lat1, lon1, lat2, lon2),
        speed_km_per_month=float(speed),
        depth_trend_km_per_month=depth_trend,
        centroid_start_lat=lat1,
        centroid_start_lon=lon1,
        centroid_end_lat=lat2,
        centroid_end_lon=lon2,
        event_count=n,
        sufficient_data=True,
    )
