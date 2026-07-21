from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.schema import ensure_event_schema, stable_event_id


def generate_demo_events(seed: int = 1755) -> pd.DataFrame:
    """Create a deterministic synthetic catalogue for UI and test demonstrations."""
    rng = np.random.default_rng(seed)
    rows = []
    ingested = datetime.now(timezone.utc)
    domains = [
        ("Margem Sudoeste Ibérica", 36.6, -10.2),
        ("Vale Inferior do Tejo", 38.9, -9.05),
    ]
    start = pd.Timestamp("2004-01-01", tz="UTC")
    end = pd.Timestamp("2026-07-01", tz="UTC")
    days = (end - start).days

    for domain_index, (domain, center_lat, center_lon) in enumerate(domains):
        count = 820 if domain_index == 0 else 510
        random_days = np.sort(rng.integers(0, days, size=count))
        for idx, day_offset in enumerate(random_days):
            time = start + pd.Timedelta(days=int(day_offset)) + pd.Timedelta(
                seconds=int(rng.integers(0, 86400))
            )
            magnitude = float(np.clip(1.4 + rng.exponential(0.55), 1.4, 4.8))
            if rng.random() < 0.006:
                magnitude = float(rng.uniform(4.0, 5.2))
            depth = float(np.clip(rng.normal(26 if domain_index == 0 else 13, 8), 2, 55))
            lat = float(center_lat + rng.normal(0, 0.55 if domain_index == 0 else 0.18))
            lon = float(center_lon + rng.normal(0, 0.9 if domain_index == 0 else 0.22))
            source_id = f"DEMO-{domain_index}-{idx}"
            rows.append(
                {
                    "event_id_memoria": stable_event_id("DEMO", source_id, time, lat, lon),
                    "source_event_id": source_id,
                    "source": "DEMO",
                    "origin_time_utc": time,
                    "latitude": lat,
                    "longitude": lon,
                    "depth_km": depth,
                    "magnitude_value": round(magnitude, 2),
                    "magnitude_type": "ML",
                    "magnitude_comparable": round(magnitude, 2),
                    "intensity_max": None,
                    "location_text": f"Demonstração sintética — {domain}",
                    "felt": bool(magnitude >= 3.5),
                    "location_uncertainty_km": 4.0,
                    "magnitude_uncertainty": 0.2,
                    "tectonic_domain": domain,
                    "domain_confidence": 1.0,
                    "historical_quality": "demo",
                    "quality_score": 0.75,
                    "record_status": "demo",
                    "source_url": None,
                    "source_file": "generated:src.demo.generate_demo_events",
                    "duplicate_group_id": None,
                    "is_preferred_record": True,
                    "ingested_at_utc": ingested,
                }
            )

    # Add deterministic clusters so the similarity and replay pages have meaningful states.
    clusters = [
        ("Margem Sudoeste Ibérica", "2009-12-10", 36.5, -10.1, 45, 3.1),
        ("Margem Sudoeste Ibérica", "2018-01-15", 36.8, -11.0, 38, 3.3),
        ("Margem Sudoeste Ibérica", "2025-08-20", 36.7, -9.8, 52, 3.5),
        ("Vale Inferior do Tejo", "2012-06-01", 38.85, -9.0, 28, 2.9),
        ("Vale Inferior do Tejo", "2024-03-10", 38.95, -9.15, 34, 3.2),
    ]
    for cluster_no, (domain, date, lat0, lon0, count, peak) in enumerate(clusters):
        base = pd.Timestamp(date, tz="UTC")
        for idx in range(count):
            time = base + pd.Timedelta(hours=int(rng.integers(0, 240)))
            magnitude = float(np.clip(rng.normal(2.05, 0.38), 1.4, peak))
            if idx == 0:
                magnitude = peak
            lat = float(lat0 + rng.normal(0, 0.08))
            lon = float(lon0 + rng.normal(0, 0.1))
            source_id = f"DEMO-CL-{cluster_no}-{idx}"
            rows.append(
                {
                    "event_id_memoria": stable_event_id("DEMO", source_id, time, lat, lon),
                    "source_event_id": source_id,
                    "source": "DEMO",
                    "origin_time_utc": time,
                    "latitude": lat,
                    "longitude": lon,
                    "depth_km": float(np.clip(rng.normal(20, 5), 4, 45)),
                    "magnitude_value": round(magnitude, 2),
                    "magnitude_type": "ML",
                    "magnitude_comparable": round(magnitude, 2),
                    "intensity_max": None,
                    "location_text": f"Cluster sintético — {domain}",
                    "felt": bool(magnitude >= 3.3),
                    "location_uncertainty_km": 3.0,
                    "magnitude_uncertainty": 0.2,
                    "tectonic_domain": domain,
                    "domain_confidence": 1.0,
                    "historical_quality": "demo",
                    "quality_score": 0.78,
                    "record_status": "demo",
                    "source_url": None,
                    "source_file": "generated:src.demo.generate_demo_events",
                    "duplicate_group_id": None,
                    "is_preferred_record": True,
                    "ingested_at_utc": ingested,
                }
            )
    return ensure_event_schema(pd.DataFrame(rows).sort_values("origin_time_utc"))
