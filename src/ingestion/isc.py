from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta

from src.common import parse_datetime, to_float, utc_now, write_json_atomic
from src.config import PATHS, load_settings
from src.http_client import create_session, ssl_verify_setting
from src.schema import concatenate_events, ensure_event_schema, stable_event_id
from src.storage import save_bronze_json

ISC_FDSN = "https://www.isc.ac.uk/fdsnws/event/1/query"
_RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

_STANDARD_COLUMNS = {
    "eventid": "event_id",
    "id": "event_id",
    "time": "time",
    "origintime": "time",
    "latitude": "latitude",
    "lat": "latitude",
    "longitude": "longitude",
    "lon": "longitude",
    "depthkm": "depth_km",
    "depth": "depth_km",
    "author": "author",
    "catalog": "catalog",
    "contributor": "contributor",
    "contributorid": "contributor_id",
    "magtype": "magnitude_type",
    "magnitudetype": "magnitude_type",
    "magnitude": "magnitude",
    "mag": "magnitude",
    "magauthor": "magnitude_author",
    "eventlocationname": "location",
    "region": "location",
    "place": "location",
    "location": "location",
}


class ISCChunkError(RuntimeError):
    """A retryable or terminal error for one ISC time range."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class ChunkFailure:
    start: datetime
    end: datetime
    error: str
    attempts: int


def _canonical_column(name: object) -> str:
    cleaned = str(name).strip().lstrip("#").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return _STANDARD_COLUMNS.get(cleaned, cleaned)


def _response_preview(text: str, limit: int = 500) -> str:
    return " ".join(text.strip().split())[:limit]


def parse_isc_response_text(text: str) -> pd.DataFrame:
    """Parse FDSN event text output separated by vertical bars."""
    if text is None or not text.strip():
        return pd.DataFrame()

    content = text.lstrip("\ufeff").strip()
    lowered = content.lower()

    if lowered.startswith("<!doctype") or lowered.startswith("<html"):
        raise ValueError(
            "O ISC devolveu HTML em vez de catálogo: "
            + _response_preview(content)
        )
    if lowered.startswith("<?xml") and "quakeml" not in lowered[:1000]:
        raise ValueError(
            "O ISC devolveu XML inesperado: "
            + _response_preview(content)
        )
    if lowered.startswith("error") or "bad request" in lowered[:500]:
        raise ValueError(
            "O ISC devolveu uma mensagem de erro: "
            + _response_preview(content)
        )

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return pd.DataFrame()

    header_index = None
    delimiter = None
    for index, line in enumerate(lines):
        candidate = line.lstrip("#").strip()
        lowered_candidate = candidate.lower()
        if "|" in candidate and "eventid" in lowered_candidate:
            header_index = index
            delimiter = "|"
            break
        if "," in candidate and "eventid" in lowered_candidate:
            header_index = index
            delimiter = ","
            break

    if header_index is None or delimiter is None:
        if any("no data" in line.lower() for line in lines):
            return pd.DataFrame()
        raise ValueError(
            "Formato ISC não reconhecido. Início da resposta: "
            + _response_preview(content)
        )

    selected = lines[header_index:]
    selected[0] = selected[0].lstrip("#").strip()
    parsed = pd.read_csv(
        StringIO("\n".join(selected)),
        sep=delimiter,
        dtype=str,
        keep_default_na=False,
        na_values=["", "NULL", "null", "NaN", "nan"],
        engine="python",
    )
    parsed.columns = [_canonical_column(column) for column in parsed.columns]

    if "event_id" in parsed.columns:
        parsed = parsed[
            parsed["event_id"].astype(str).str.lower() != "eventid"
        ]

    return parsed.reset_index(drop=True)


def normalise_isc_frame(
    raw: pd.DataFrame,
    source_file: str = "",
    source_url: str = ISC_FDSN,
) -> pd.DataFrame:
    if raw.empty:
        return ensure_event_schema(pd.DataFrame())

    frame = raw.copy()
    frame.columns = [_canonical_column(column) for column in frame.columns]
    ingested = utc_now()
    rows: list[dict[str, Any]] = []

    for idx, record in frame.iterrows():
        origin = parse_datetime(record.get("time"))
        latitude = to_float(record.get("latitude"))
        longitude = to_float(record.get("longitude"))

        if pd.isna(origin) or latitude is None or longitude is None:
            continue

        source_id_value = record.get("event_id")
        source_id = (
            str(source_id_value).strip()
            if pd.notna(source_id_value) and str(source_id_value).strip()
            else str(idx)
        )
        magnitude = to_float(record.get("magnitude"))
        magnitude_type_value = record.get("magnitude_type")
        magnitude_type = (
            str(magnitude_type_value).strip()
            if pd.notna(magnitude_type_value)
            and str(magnitude_type_value).strip()
            else None
        )
        location_value = record.get("location")
        location = (
            str(location_value).strip()
            if pd.notna(location_value) and str(location_value).strip()
            else None
        )
        depth = to_float(record.get("depth_km"))

        quality = 0.92
        if magnitude is None:
            quality -= 0.08
        if depth is None:
            quality -= 0.05
        if location is None:
            quality -= 0.03

        rows.append(
            {
                "event_id_memoria": stable_event_id(
                    "ISC", source_id, origin, latitude, longitude
                ),
                "source_event_id": source_id,
                "source": "ISC",
                "origin_time_utc": origin,
                "latitude": latitude,
                "longitude": longitude,
                "depth_km": depth,
                "magnitude_value": magnitude,
                "magnitude_type": magnitude_type,
                "magnitude_comparable": magnitude,
                "intensity_max": None,
                "location_text": location,
                "felt": None,
                "location_uncertainty_km": None,
                "magnitude_uncertainty": None,
                "tectonic_domain": None,
                "domain_confidence": None,
                "historical_quality": "high",
                "quality_score": max(0.0, quality),
                "record_status": "reviewed",
                "source_url": source_url,
                "source_file": source_file,
                "duplicate_group_id": None,
                "is_preferred_record": True,
                "ingested_at_utc": ingested,
            }
        )

    return ensure_event_schema(pd.DataFrame(rows))


def normalise_isc_response(
    text: str,
    source_file: str = "",
    source_url: str = ISC_FDSN,
) -> pd.DataFrame:
    return normalise_isc_frame(
        parse_isc_response_text(text),
        source_file=source_file,
        source_url=source_url,
    )


def _parse_date(value: str) -> datetime:
    parsed = pd.to_datetime(value, utc=True, errors="raise")
    return parsed.to_pydatetime()


def _date_chunks_months(
    start_time: str,
    end_time: str,
    chunk_months: int,
) -> Iterable[tuple[datetime, datetime]]:
    if chunk_months < 1:
        raise ValueError("chunk_months deve ser pelo menos 1.")

    start = _parse_date(start_time)
    end = min(_parse_date(end_time), datetime.now(timezone.utc))
    if start >= end:
        raise ValueError("A data inicial tem de ser anterior à data final efetiva.")

    current = start
    while current < end:
        next_end = min(current + relativedelta(months=chunk_months), end)
        yield current, next_end
        current = next_end


def _query_key(
    start: datetime,
    end: datetime,
    min_latitude: float,
    max_latitude: float,
    min_longitude: float,
    max_longitude: float,
    min_magnitude: float | None,
) -> str:
    raw = "|".join(
        [
            start.isoformat(),
            end.isoformat(),
            str(min_latitude),
            str(max_latitude),
            str(min_longitude),
            str(max_longitude),
            str(min_magnitude),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _checkpoint_file(query_id: str) -> Path:
    path = PATHS.bronze / "isc" / "checkpoints" / f"{query_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_checkpoint(query_id: str) -> dict[str, Any]:
    path = _checkpoint_file(query_id)
    if not path.exists():
        return {"completed": {}, "failed": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"completed": {}, "failed": {}}


def _save_checkpoint(query_id: str, checkpoint: dict[str, Any]) -> None:
    write_json_atomic(_checkpoint_file(query_id), checkpoint)


def _range_key(start: datetime, end: datetime) -> str:
    return f"{start.isoformat()}__{end.isoformat()}"


def _load_completed_frame(entry: dict[str, Any]) -> pd.DataFrame | None:
    bronze_file = entry.get("bronze_file")
    if not bronze_file:
        return None
    path = Path(bronze_file)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        response_text = payload.get("response_text") or payload.get("response_csv")
        if response_text is None:
            return None
        return normalise_isc_response(
            response_text,
            source_file=str(path),
            source_url=payload.get("response_url", ISC_FDSN),
        )
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None


def _request_isc_once(
    start: datetime,
    end: datetime,
    min_latitude: float,
    max_latitude: float,
    min_longitude: float,
    max_longitude: float,
    min_magnitude: float | None,
    client: requests.Session,
    connect_timeout: int,
    read_timeout: int,
) -> tuple[pd.DataFrame, Path, dict[str, Any]]:
    settings = load_settings()
    params: dict[str, Any] = {
        "format": "text",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "minlatitude": min_latitude,
        "maxlatitude": max_latitude,
        "minlongitude": min_longitude,
        "maxlongitude": max_longitude,
        "nodata": 204,
    }
    if min_magnitude is not None:
        params["minmagnitude"] = min_magnitude

    try:
        response = client.get(
            ISC_FDSN,
            params=params,
            timeout=(connect_timeout, read_timeout),
            headers={"User-Agent": settings["user_agent"]},
            verify=ssl_verify_setting(),
        )
    except requests.exceptions.Timeout as error:
        raise ISCChunkError(
            f"timeout após {read_timeout}s para {start:%Y-%m-%d} → {end:%Y-%m-%d}",
            retryable=True,
        ) from error
    except requests.exceptions.ConnectionError as error:
        raise ISCChunkError(
            f"erro de ligação para {start:%Y-%m-%d} → {end:%Y-%m-%d}: {error}",
            retryable=True,
        ) from error

    if response.status_code in _RETRYABLE_STATUS_CODES:
        raise ISCChunkError(
            f"HTTP {response.status_code} para {start:%Y-%m-%d} → {end:%Y-%m-%d}",
            retryable=True,
        )
    if response.status_code == 204:
        payload = {
            "request": params,
            "status_code": 204,
            "response_text": "",
            "record_count": 0,
            "response_url": response.url,
        }
        path = save_bronze_json(
            "isc", payload, f"events_{start:%Y%m%d}_{end:%Y%m%d}"
        )
        return ensure_event_schema(pd.DataFrame()), path, payload

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as error:
        raise ISCChunkError(
            f"HTTP {response.status_code}: {_response_preview(response.text)}",
            retryable=False,
        ) from error

    response_text = response.text
    try:
        raw = parse_isc_response_text(response_text)
    except ValueError as error:
        raise ISCChunkError(str(error), retryable=False) from error

    normalised = normalise_isc_frame(raw, source_url=response.url)
    payload = {
        "request": params,
        "status_code": response.status_code,
        "content_type": response.headers.get("Content-Type"),
        "response_text": response_text,
        "response_csv": response_text,
        "parsed_row_count": int(len(raw)),
        "record_count": int(len(normalised)),
        "response_url": response.url,
    }
    path = save_bronze_json(
        "isc", payload, f"events_{start:%Y%m%d}_{end:%Y%m%d}"
    )
    if not normalised.empty:
        normalised["source_file"] = str(path)
    return normalised, path, payload


def _request_with_retries(
    start: datetime,
    end: datetime,
    *,
    min_latitude: float,
    max_latitude: float,
    min_longitude: float,
    max_longitude: float,
    min_magnitude: float | None,
    client: requests.Session,
    connect_timeout: int,
    read_timeout: int,
    max_retries: int,
) -> tuple[pd.DataFrame, Path, dict[str, Any], int]:
    attempts = max(1, max_retries + 1)
    last_error: ISCChunkError | None = None
    for attempt in range(1, attempts + 1):
        print(
            f"ISC {start:%Y-%m-%d} → {end:%Y-%m-%d} "
            f"· tentativa {attempt}/{attempts}"
        )
        try:
            frame, path, payload = _request_isc_once(
                start,
                end,
                min_latitude,
                max_latitude,
                min_longitude,
                max_longitude,
                min_magnitude,
                client,
                connect_timeout,
                read_timeout,
            )
            return frame, path, payload, attempt
        except ISCChunkError as error:
            last_error = error
            if not error.retryable or attempt >= attempts:
                break
            delay = min(20.0, 2.0 ** (attempt - 1))
            print(f"  ↳ {error}. Nova tentativa em {delay:.0f}s.")
            time.sleep(delay)

    assert last_error is not None
    raise last_error


def _midpoint(start: datetime, end: datetime) -> datetime:
    span = end - start
    midpoint = start + span / 2
    # Hour precision avoids overlapping or missing seconds while producing
    # readable deterministic ranges.
    midpoint = midpoint.replace(minute=0, second=0, microsecond=0)
    if midpoint <= start:
        midpoint = start + timedelta(days=1)
    if midpoint >= end:
        midpoint = end - timedelta(days=1)
    return midpoint


def _adaptive_fetch(
    start: datetime,
    end: datetime,
    *,
    min_latitude: float,
    max_latitude: float,
    min_longitude: float,
    max_longitude: float,
    min_magnitude: float | None,
    client: requests.Session,
    connect_timeout: int,
    read_timeout: int,
    max_retries: int,
    min_chunk_days: int,
    checkpoint: dict[str, Any],
    query_id: str,
) -> tuple[list[pd.DataFrame], list[dict[str, Any]], list[ChunkFailure]]:
    key = _range_key(start, end)
    completed = checkpoint.setdefault("completed", {})
    cached = completed.get(key)
    if cached:
        frame = _load_completed_frame(cached)
        if frame is not None:
            print(
                f"ISC {start:%Y-%m-%d} → {end:%Y-%m-%d}: "
                f"retomado do Bronze ({len(frame)} registos)"
            )
            return [frame], [cached], []

    try:
        frame, path, payload, attempts = _request_with_retries(
            start,
            end,
            min_latitude=min_latitude,
            max_latitude=max_latitude,
            min_longitude=min_longitude,
            max_longitude=max_longitude,
            min_magnitude=min_magnitude,
            client=client,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            max_retries=max_retries,
        )
        entry = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "records": int(len(frame)),
            "bronze_file": str(path),
            "status_code": payload.get("status_code"),
            "attempts": attempts,
        }
        completed[key] = entry
        checkpoint.setdefault("failed", {}).pop(key, None)
        _save_checkpoint(query_id, checkpoint)
        print(
            f"  ✓ {start:%Y-%m-%d} → {end:%Y-%m-%d}: "
            f"{len(frame)} registos"
        )
        return [frame], [entry], []

    except ISCChunkError as error:
        duration_days = max(1, (end - start).days)
        if error.retryable and duration_days > min_chunk_days:
            split = _midpoint(start, end)
            print(
                f"  ↳ {error}. Intervalo dividido em "
                f"{start:%Y-%m-%d} → {split:%Y-%m-%d} e "
                f"{split:%Y-%m-%d} → {end:%Y-%m-%d}."
            )
            left = _adaptive_fetch(
                start,
                split,
                min_latitude=min_latitude,
                max_latitude=max_latitude,
                min_longitude=min_longitude,
                max_longitude=max_longitude,
                min_magnitude=min_magnitude,
                client=client,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                max_retries=max_retries,
                min_chunk_days=min_chunk_days,
                checkpoint=checkpoint,
                query_id=query_id,
            )
            right = _adaptive_fetch(
                split,
                end,
                min_latitude=min_latitude,
                max_latitude=max_latitude,
                min_longitude=min_longitude,
                max_longitude=max_longitude,
                min_magnitude=min_magnitude,
                client=client,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                max_retries=max_retries,
                min_chunk_days=min_chunk_days,
                checkpoint=checkpoint,
                query_id=query_id,
            )
            return (
                left[0] + right[0],
                left[1] + right[1],
                left[2] + right[2],
            )

        failure = ChunkFailure(
            start=start,
            end=end,
            error=str(error),
            attempts=max_retries + 1,
        )
        checkpoint.setdefault("failed", {})[key] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "error": str(error),
            "attempts": max_retries + 1,
        }
        _save_checkpoint(query_id, checkpoint)
        print(f"  ✗ Falha definitiva: {error}")
        return [], [], [failure]


def fetch_isc_events(
    start_time: str,
    end_time: str,
    min_latitude: float = 32.0,
    max_latitude: float = 44.0,
    min_longitude: float = -20.0,
    max_longitude: float = -5.0,
    min_magnitude: float | None = None,
    session: requests.Session | None = None,
    chunk_months: int = 6,
    chunk_years: int | None = None,
    min_chunk_days: int = 7,
    max_retries: int = 1,
    connect_timeout: int = 20,
    read_timeout: int = 120,
    continue_on_error: bool = False,
) -> tuple[pd.DataFrame, Path]:
    """Retrieve ISC events with retries, adaptive splitting and checkpoints."""
    if chunk_years is not None:
        chunk_months = max(1, int(chunk_years) * 12)
    if min_chunk_days < 1:
        raise ValueError("min_chunk_days deve ser pelo menos 1.")
    if max_retries < 0:
        raise ValueError("max_retries não pode ser negativo.")

    client = session or create_session()
    request_start = _parse_date(start_time)
    request_end = min(_parse_date(end_time), datetime.now(timezone.utc))
    query_id = _query_key(
        request_start,
        request_end,
        min_latitude,
        max_latitude,
        min_longitude,
        max_longitude,
        min_magnitude,
    )
    checkpoint = _load_checkpoint(query_id)
    checkpoint.update(
        {
            "query_id": query_id,
            "requested_start": start_time,
            "requested_end": end_time,
            "effective_end": request_end.isoformat(),
            "bounds": {
                "min_latitude": min_latitude,
                "max_latitude": max_latitude,
                "min_longitude": min_longitude,
                "max_longitude": max_longitude,
                "min_magnitude": min_magnitude,
            },
        }
    )
    _save_checkpoint(query_id, checkpoint)

    frames: list[pd.DataFrame] = []
    successful_chunks: list[dict[str, Any]] = []
    failures: list[ChunkFailure] = []

    for chunk_start, chunk_end in _date_chunks_months(
        start_time, end_time, chunk_months
    ):
        result_frames, result_chunks, result_failures = _adaptive_fetch(
            chunk_start,
            chunk_end,
            min_latitude=min_latitude,
            max_latitude=max_latitude,
            min_longitude=min_longitude,
            max_longitude=max_longitude,
            min_magnitude=min_magnitude,
            client=client,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            max_retries=max_retries,
            min_chunk_days=min_chunk_days,
            checkpoint=checkpoint,
            query_id=query_id,
        )
        frames.extend(result_frames)
        successful_chunks.extend(result_chunks)
        failures.extend(result_failures)

    combined = concatenate_events(frames)
    if not combined.empty:
        combined = combined.drop_duplicates(
            subset=["event_id_memoria"], keep="last"
        ).reset_index(drop=True)

    status = "complete" if not failures else ("partial" if frames else "failed")
    manifest_payload = {
        "source": "ISC",
        "query_id": query_id,
        "status": status,
        "requested_start": start_time,
        "requested_end": end_time,
        "effective_end": request_end.isoformat(),
        "chunk_months": chunk_months,
        "min_chunk_days": min_chunk_days,
        "max_retries": max_retries,
        "connect_timeout": connect_timeout,
        "read_timeout": read_timeout,
        "bounds": checkpoint["bounds"],
        "total_records": int(len(combined)),
        "successful_chunks": successful_chunks,
        "failed_chunks": [
            {
                "start": item.start.isoformat(),
                "end": item.end.isoformat(),
                "error": item.error,
                "attempts": item.attempts,
            }
            for item in failures
        ],
        "checkpoint_file": str(_checkpoint_file(query_id)),
    }
    manifest_path = save_bronze_json(
        "isc", manifest_payload, f"manifest_{start_time}_{end_time}"
    )

    if failures and not continue_on_error:
        failed_summary = "; ".join(
            f"{item.start:%Y-%m-%d}→{item.end:%Y-%m-%d}: {item.error}"
            for item in failures[:5]
        )
        raise RuntimeError(
            f"A ingestão ISC ficou incompleta: {len(failures)} intervalo(s) "
            f"falharam. Os intervalos concluídos foram guardados e serão "
            f"retomados automaticamente na próxima execução. Manifesto: "
            f"{manifest_path}. Falhas: {failed_summary}"
        )

    return ensure_event_schema(combined), manifest_path


def diagnose_isc_bronze_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    text = payload.get("response_text") or payload.get("response_csv") or ""
    result: dict[str, Any] = {
        "file": str(file_path),
        "request": payload.get("request"),
        "status_code": payload.get("status_code"),
        "content_type": payload.get("content_type"),
        "characters": len(text),
        "preview": _response_preview(text, 1000),
    }
    try:
        parsed = parse_isc_response_text(text)
        result["parsed_rows"] = int(len(parsed))
        result["columns"] = list(parsed.columns)
        result["parser_error"] = None
    except ValueError as error:
        result["parsed_rows"] = 0
        result["columns"] = []
        result["parser_error"] = str(error)
    return result
