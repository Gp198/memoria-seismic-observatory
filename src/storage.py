from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.common import sha256_bytes, write_json_atomic
from src.config import PATHS
from src.schema import ensure_event_schema


def timestamp_slug(moment: datetime | None = None) -> str:
    moment = moment or datetime.now(timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def save_bronze_json(source: str, payload: Any, descriptor: str) -> Path:
    PATHS.ensure()
    now = datetime.now(timezone.utc)
    folder = PATHS.bronze / source.lower() / now.strftime("%Y/%m/%d")
    path = folder / f"{descriptor}_{timestamp_slug(now)}.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    write_json_atomic(path, payload)
    digest_path = path.with_suffix(".sha256")
    digest_path.write_text(sha256_bytes(content) + "\n", encoding="utf-8")
    return path


def _temporary_path(final_path: Path) -> Path:
    return final_path.with_name(
        f".{final_path.name}.{uuid.uuid4().hex}.tmp"
    )


def _write_metadata(base_path: Path, frame: pd.DataFrame, parquet_written: bool) -> None:
    source_counts: dict[str, int] = {}
    if "source" in frame.columns:
        source_counts = {
            str(key): int(value)
            for key, value in frame["source"].astype("string").value_counts(dropna=False).items()
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(frame)),
        "columns": list(frame.columns),
        "parquet_written": parquet_written,
        "source_counts": source_counts,
    }
    write_json_atomic(base_path.with_suffix(".metadata.json"), payload)


def save_dataframe(frame: pd.DataFrame, base_path: Path) -> tuple[Path | None, Path]:
    """Atomically persist CSV and Parquet.

    CSV is the guaranteed format. Parquet is preferred when available. If a
    Parquet write fails, any older Parquet file is removed so the loader cannot
    silently read stale data from a previous run.
    """
    base_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = base_path.with_suffix(".csv")
    parquet_path = base_path.with_suffix(".parquet")
    csv_temp = _temporary_path(csv_path)
    parquet_temp = _temporary_path(parquet_path)

    try:
        frame.to_csv(csv_temp, index=False)
        os.replace(csv_temp, csv_path)
    except Exception:
        csv_temp.unlink(missing_ok=True)
        raise

    parquet_written = False
    try:
        frame.to_parquet(parquet_temp, index=False)
        os.replace(parquet_temp, parquet_path)
        parquet_written = True
    except Exception as error:
        parquet_temp.unlink(missing_ok=True)
        # Critical: do not keep an older Parquet that would shadow the new CSV.
        parquet_path.unlink(missing_ok=True)
        print(
            f"WARNING: Parquet was not written for {base_path.name}: "
            f"{type(error).__name__}: {error}. CSV remains available."
        )

    _write_metadata(base_path, frame, parquet_written)
    return (parquet_path if parquet_written else None), csv_path


def load_dataframe(base_path: Path) -> pd.DataFrame:
    parquet_path = base_path.with_suffix(".parquet")
    csv_path = base_path.with_suffix(".csv")

    # Prefer Parquet only when it is at least as recent as CSV. This prevents a
    # stale Parquet from shadowing a newer successful CSV write.
    if parquet_path.exists() and (
        not csv_path.exists() or parquet_path.stat().st_mtime >= csv_path.stat().st_mtime
    ):
        return pd.read_parquet(parquet_path)
    if csv_path.exists():
        return pd.read_csv(csv_path)
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    raise FileNotFoundError(f"No dataset found at {parquet_path} or {csv_path}")


def save_silver_events(frame: pd.DataFrame) -> tuple[Path | None, Path]:
    clean = ensure_event_schema(frame)
    return save_dataframe(clean, PATHS.silver / "events")


def load_silver_events() -> pd.DataFrame:
    return ensure_event_schema(load_dataframe(PATHS.silver / "events"))


def save_gold_fingerprints(frame: pd.DataFrame) -> tuple[Path | None, Path]:
    return save_dataframe(frame, PATHS.gold / "fingerprints")


def load_gold_fingerprints() -> pd.DataFrame:
    frame = load_dataframe(PATHS.gold / "fingerprints")
    for column in ["window_start", "window_end"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    return frame


def remove_derived_outputs() -> list[Path]:
    removed: list[Path] = []
    candidates = [
        PATHS.silver / "events.csv",
        PATHS.silver / "events.parquet",
        PATHS.silver / "events.metadata.json",
        PATHS.gold / "fingerprints.csv",
        PATHS.gold / "fingerprints.parquet",
        PATHS.gold / "fingerprints.metadata.json",
        PATHS.gold / "fingerprints_complete.csv",
        PATHS.gold / "fingerprints_complete.parquet",
        PATHS.gold / "fingerprints_complete.metadata.json",
        PATHS.gold / "fingerprints_declustered.csv",
        PATHS.gold / "fingerprints_declustered.parquet",
        PATHS.gold / "fingerprints_declustered.metadata.json",
        PATHS.gold / "fingerprints_complete_operational.csv",
        PATHS.gold / "fingerprints_complete_operational.parquet",
        PATHS.gold / "fingerprints_complete_operational.metadata.json",
        PATHS.gold / "fingerprints_complete_validated.csv",
        PATHS.gold / "fingerprints_complete_validated.parquet",
        PATHS.gold / "fingerprints_complete_validated.metadata.json",
        PATHS.gold / "fingerprints_declustered_operational.csv",
        PATHS.gold / "fingerprints_declustered_operational.parquet",
        PATHS.gold / "fingerprints_declustered_operational.metadata.json",
        PATHS.gold / "fingerprints_declustered_validated.csv",
        PATHS.gold / "fingerprints_declustered_validated.parquet",
        PATHS.gold / "fingerprints_declustered_validated.metadata.json",
        PATHS.reports / "latest_report.md",
    ]
    for path in candidates:
        if path.exists():
            path.unlink()
            removed.append(path)
    for pattern in (
        "validation_scores_*",
        "validation_summary_*",
    ):
        for path in PATHS.gold.glob(pattern):
            if path.is_file():
                path.unlink()
                removed.append(path)
    return removed
