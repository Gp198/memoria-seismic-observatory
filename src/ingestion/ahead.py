from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.common import first_present, parse_datetime, to_float, utc_now
from src.config import load_settings
from src.http_client import create_session, ssl_verify_setting
from src.schema import ensure_event_schema, stable_event_id
from src.storage import save_bronze_json

AHEAD_WFS = "https://www.emidius.eu/services/europe/wfs"


def fetch_ahead_epica(
    min_latitude: float = 32.0,
    max_latitude: float = 44.0,
    min_longitude: float = -20.0,
    max_longitude: float = -5.0,
    minimum_mw: float | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, Path]:
    filters = [
        f"Lat>={min_latitude}",
        f"Lat<={max_latitude}",
        f"Lon>={min_longitude}",
        f"Lon<={max_longitude}",
    ]
    if minimum_mw is not None:
        filters.append(f"Mw>={minimum_mw}")
    params: dict[str, Any] = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": "europe:EPICA_1000_1899",
        "outputFormat": "application/json",
        "CQL_FILTER": " AND ".join(filters),
    }
    settings = load_settings()
    client = session or create_session()
    response = client.get(
        AHEAD_WFS,
        params=params,
        timeout=settings["request_timeout_seconds"],
        headers={"User-Agent": settings["user_agent"]},
        verify=ssl_verify_setting(),
    )
    response.raise_for_status()
    payload = response.json()
    path = save_bronze_json("ahead", payload, "epica_portugal")
    return normalise_ahead_payload(payload, str(path), response.url), path


def normalise_ahead_payload(
    payload: dict[str, Any],
    source_file: str = "",
    source_url: str = AHEAD_WFS,
) -> pd.DataFrame:
    features = payload.get("features", []) if isinstance(payload, dict) else []
    ingested = utc_now()
    rows = []
    for idx, feature in enumerate(features):
        properties = dict(feature.get("properties") or {})
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        lat = to_float(first_present(properties, ["Lat", "lat", "latitude"]))
        lon = to_float(first_present(properties, ["Lon", "lon", "longitude"]))
        if (lat is None or lon is None) and len(coords) >= 2:
            lon, lat = to_float(coords[0]), to_float(coords[1])
        if lat is None or lon is None:
            continue
        year = first_present(properties, ["Year", "year"])
        month = int(to_float(first_present(properties, ["Mo", "month"], 1)) or 1)
        day = int(to_float(first_present(properties, ["Da", "day"], 1)) or 1)
        hour = int(to_float(first_present(properties, ["Ho", "hour"], 0)) or 0)
        minute = int(to_float(first_present(properties, ["Mi", "minute"], 0)) or 0)
        origin = parse_datetime(f"{int(float(year)):04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00")
        source_id = str(first_present(properties, ["EqID", "eqid", "id"], idx))
        magnitude = to_float(first_present(properties, ["Mw", "mw", "CMw", "MMw"]))
        rows.append(
            {
                "event_id_memoria": stable_event_id("AHEAD", source_id, origin, lat, lon),
                "source_event_id": source_id,
                "source": "AHEAD",
                "origin_time_utc": origin,
                "latitude": lat,
                "longitude": lon,
                "depth_km": to_float(first_present(properties, ["H", "depth"])),
                "magnitude_value": magnitude,
                "magnitude_type": "Mw" if magnitude is not None else None,
                "magnitude_comparable": magnitude,
                "intensity_max": first_present(properties, ["Ix", "Io", "CIo"]),
                "location_text": first_present(properties, ["Ax", "area", "Reg"]),
                "felt": None,
                "location_uncertainty_km": max(
                    [
                        value
                        for value in [
                            to_float(first_present(properties, ["LatUnc"])),
                            to_float(first_present(properties, ["LonUnc"])),
                        ]
                        if value is not None
                    ],
                    default=None,
                ),
                "magnitude_uncertainty": to_float(
                    first_present(properties, ["MwUnc", "CMwUnc", "MMwUnc"])
                ),
                "tectonic_domain": None,
                "domain_confidence": None,
                "historical_quality": "medium",
                "quality_score": 0.72 if magnitude is not None else 0.58,
                "record_status": "historical",
                "source_url": source_url,
                "source_file": source_file,
                "duplicate_group_id": None,
                "is_preferred_record": True,
                "ingested_at_utc": ingested,
            }
        )
    return ensure_event_schema(pd.DataFrame(rows))
