from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def first_present(record: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return default


def to_float(value: Any) -> float | None:
    try:
        if value in (None, "", "null", "None"):
            return None
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def to_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "sim", "s", "felt"}:
        return True
    if lowered in {"false", "0", "no", "não", "nao", "n"}:
        return False
    return None


def parse_datetime(value: Any, date_value: Any = None, time_value: Any = None) -> pd.Timestamp:
    candidates = [value]
    if date_value is not None:
        combined = f"{date_value} {time_value or ''}".strip()
        candidates.append(combined)
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        parsed = pd.to_datetime(candidate, utc=True, errors="coerce", dayfirst=False)
        if not pd.isna(parsed):
            return parsed
        parsed = pd.to_datetime(candidate, utc=True, errors="coerce", dayfirst=True)
        if not pd.isna(parsed):
            return parsed
    return pd.NaT


def haversine_km(
    lat1: float | np.ndarray,
    lon1: float | np.ndarray,
    lat2: float | np.ndarray,
    lon2: float | np.ndarray,
) -> float | np.ndarray:
    lat1_r, lon1_r, lat2_r, lon2_r = map(
        np.radians, [lat1, lon1, lat2, lon2]
    )
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def seismic_energy_joule(magnitude: float | pd.Series) -> float | pd.Series:
    return 10 ** (1.5 * magnitude + 4.8)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    temp.replace(path)


def safe_json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
