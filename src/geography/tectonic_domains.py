from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape

from src.config import PATHS
from src.schema import ensure_event_schema


@dataclass(frozen=True)
class Domain:
    domain_id: str
    name: str
    version: str
    geometry: object
    authority: str


def load_domains(path: str | Path | None = None) -> list[Domain]:
    path = Path(path) if path else PATHS.config / "domains.geojson"
    payload = json.loads(path.read_text(encoding="utf-8"))
    domains = []
    for feature in payload["features"]:
        properties = feature["properties"]
        domains.append(
            Domain(
                domain_id=properties["domain_id"],
                name=properties["name"],
                version=properties["version"],
                geometry=shape(feature["geometry"]),
                authority=properties.get("authority", "unknown"),
            )
        )
    return domains


def classify_point(latitude: float, longitude: float, domains: list[Domain] | None = None) -> tuple[str, float]:
    domains = domains or load_domains()
    point = Point(float(longitude), float(latitude))
    containing = [domain for domain in domains if domain.geometry.covers(point)]
    if len(containing) == 1:
        return containing[0].name, 0.9
    if len(containing) > 1:
        smallest = min(containing, key=lambda domain: domain.geometry.area)
        # Overlap is expected for broad pilot polygons; the smaller domain is more specific.
        return smallest.name, 0.85
    distances = sorted(
        ((float(domain.geometry.distance(point)), domain) for domain in domains),
        key=lambda item: item[0],
    )
    if distances and distances[0][0] <= 0.25:
        return distances[0][1].name, 0.45
    return "Fora dos domínios piloto", 0.2


def classify_events(frame: pd.DataFrame, domains: list[Domain] | None = None) -> pd.DataFrame:
    events = ensure_event_schema(frame).copy()
    domains = domains or load_domains()
    classifications = [
        classify_point(row.latitude, row.longitude, domains)
        if pd.notna(row.latitude) and pd.notna(row.longitude)
        else ("Não classificado", 0.0)
        for row in events.itertuples()
    ]
    events["tectonic_domain"] = [item[0] for item in classifications]
    events["domain_confidence"] = [item[1] for item in classifications]
    return ensure_event_schema(events)
