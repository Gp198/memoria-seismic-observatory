from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import requests

from src.common import first_present, parse_datetime, to_bool, to_float, utc_now
from src.config import load_settings
from src.http_client import create_session, ssl_verify_setting
from src.schema import ensure_event_schema, stable_event_id
from src.storage import save_bronze_json

IPMA_BASE = "https://api.ipma.pt/open-data/observation/seismic"


def fetch_ipma_area(area_id: int = 7, session: requests.Session | None = None) -> tuple[dict[str, Any], Path]:
    settings = load_settings()
    client = session or create_session()
    url = f"{IPMA_BASE}/{area_id}.json"
    response = client.get(
        url,
        timeout=settings["request_timeout_seconds"],
        headers={"User-Agent": settings["user_agent"]},
        verify=ssl_verify_setting(),
    )
    response.raise_for_status()
    payload = response.json()
    source_path = save_bronze_json("ipma", payload, f"area_{area_id}")
    return payload, source_path


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "events", "features", "observations"):
        value = payload.get(key)
        if isinstance(value, list):
            if key == "features":
                records: list[dict[str, Any]] = []
                for feature in value:
                    if not isinstance(feature, dict):
                        continue
                    properties = dict(feature.get("properties") or {})
                    geometry = feature.get("geometry") or {}
                    coords = geometry.get("coordinates") or []
                    if len(coords) >= 2:
                        properties.setdefault("longitude", coords[0])
                        properties.setdefault("latitude", coords[1])
                    records.append(properties)
                return records
            return [item for item in value if isinstance(item, dict)]
    return []


def normalise_ipma_payload(
    payload: Any,
    source_file: str = "",
    source_url: str = IPMA_BASE,
) -> pd.DataFrame:
    ingested = utc_now()
    rows: list[dict[str, Any]] = []
    for raw in _extract_records(payload):
        source_event_id = str(
            first_present(raw, ["id", "eventId", "event_id", "eventID", "shakeMapId"], "")
        )
        origin = parse_datetime(
            first_present(raw, ["time", "datetime", "dateTime", "originTime", "obsTime"]),
            first_present(raw, ["date", "data"]),
            first_present(raw, ["hour", "hora"]),
        )
        latitude = to_float(first_present(raw, ["latitude", "lat", "Lat"]))
        longitude = to_float(first_present(raw, ["longitude", "lon", "lng", "Lon"]))
        magnitude = to_float(
            first_present(raw, ["magnitud", "magnitude", "mag", "Magnitude", "Mw", "ML"])
        )
        magnitude_type = first_present(raw, ["magType", "magnitudeType", "typeMagnitude"], "ML")
        depth = to_float(first_present(raw, ["depth", "depthKm", "profundidade", "H"]))
        intensity = first_present(raw, ["degree", "intensity", "maxIntensity", "Io"])
        location_text = first_present(
            raw,
            ["local", "location", "region", "obsRegion", "description", "epicentralArea"],
        )
        felt = to_bool(first_present(raw, ["sensed", "felt", "sentido"]))
        if felt is None and intensity not in (None, "", "0"):
            felt = True
        if pd.isna(origin) or latitude is None or longitude is None:
            continue
        event_id = stable_event_id("IPMA", source_event_id, origin, latitude, longitude)
        rows.append(
            {
                "event_id_memoria": event_id,
                "source_event_id": source_event_id or event_id,
                "source": "IPMA",
                "origin_time_utc": origin,
                "latitude": latitude,
                "longitude": longitude,
                "depth_km": depth,
                "magnitude_value": magnitude,
                "magnitude_type": str(magnitude_type or "ML"),
                "magnitude_comparable": magnitude,
                "intensity_max": intensity,
                "location_text": location_text,
                "felt": felt,
                "location_uncertainty_km": None,
                "magnitude_uncertainty": None,
                "tectonic_domain": None,
                "domain_confidence": None,
                "historical_quality": "high",
                "quality_score": 0.92 if magnitude is not None and depth is not None else 0.82,
                "record_status": "preliminary",
                "source_url": source_url,
                "source_file": source_file,
                "duplicate_group_id": None,
                "is_preferred_record": True,
                "ingested_at_utc": ingested,
            }
        )
    return ensure_event_schema(pd.DataFrame(rows))


def ingest_ipma_areas(areas: list[int] | tuple[int, ...] = (7, 3)) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for area in areas:
        payload, path = fetch_ipma_area(area)
        frames.append(
            normalise_ipma_payload(
                payload,
                source_file=str(path),
                source_url=f"{IPMA_BASE}/{area}.json",
            )
        )
    if not frames:
        return ensure_event_schema(pd.DataFrame())
    return ensure_event_schema(pd.concat(frames, ignore_index=True))


def import_ipma_historical_csv(
    path: str | Path,
    column_mapping: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Import a manually downloaded or transcribed historical IPMA CSV.

    The optional mapping maps canonical names to source column names, for example:
    {"origin_time_utc": "DataHora", "latitude": "Lat", "longitude": "Lon"}.
    """
    path = Path(path)
    raw = pd.read_csv(path)
    mapping = {
        "source_event_id": "event_id",
        "origin_time_utc": "origin_time",
        "latitude": "latitude",
        "longitude": "longitude",
        "depth_km": "depth_km",
        "magnitude_value": "magnitude",
        "magnitude_type": "magnitude_type",
        "intensity_max": "intensity",
        "location_text": "location",
    }
    if column_mapping:
        mapping.update(column_mapping)

    rows = []
    ingested = utc_now()
    for idx, record in raw.iterrows():
        origin = parse_datetime(record.get(mapping["origin_time_utc"]))
        lat = to_float(record.get(mapping["latitude"]))
        lon = to_float(record.get(mapping["longitude"]))
        if pd.isna(origin) or lat is None or lon is None:
            continue
        source_id = str(record.get(mapping["source_event_id"], idx))
        magnitude = to_float(record.get(mapping["magnitude_value"]))
        rows.append(
            {
                "event_id_memoria": stable_event_id("IPMA_HISTORICAL", source_id, origin, lat, lon),
                "source_event_id": source_id,
                "source": "IPMA_HISTORICAL",
                "origin_time_utc": origin,
                "latitude": lat,
                "longitude": lon,
                "depth_km": to_float(record.get(mapping["depth_km"])),
                "magnitude_value": magnitude,
                "magnitude_type": record.get(mapping["magnitude_type"], None),
                "magnitude_comparable": magnitude,
                "intensity_max": record.get(mapping["intensity_max"], None),
                "location_text": record.get(mapping["location_text"], None),
                "felt": None,
                "location_uncertainty_km": None,
                "magnitude_uncertainty": None,
                "tectonic_domain": None,
                "domain_confidence": None,
                "historical_quality": "medium",
                "quality_score": 0.72,
                "record_status": "historical",
                "source_url": None,
                "source_file": str(path),
                "duplicate_group_id": None,
                "is_preferred_record": True,
                "ingested_at_utc": ingested,
            }
        )
    return ensure_event_schema(pd.DataFrame(rows))
