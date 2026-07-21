from pathlib import Path

import pandas as pd

from src.schema import ensure_event_schema
from src.storage import load_dataframe, save_dataframe


def test_mixed_source_event_ids_are_normalised(tmp_path: Path):
    frame = ensure_event_schema(
        pd.DataFrame(
            {
                "event_id_memoria": ["a", "b"],
                "source_event_id": [1001, "A-2"],
                "source": ["AHEAD", "IPMA"],
                "origin_time_utc": ["1755-11-01T09:40:00Z", "2026-01-01T00:00:00Z"],
                "latitude": [36.0, 38.0],
                "longitude": [-10.0, -9.0],
                "is_preferred_record": [True, True],
            }
        )
    )
    assert str(frame["source_event_id"].dtype) == "string"
    parquet, csv = save_dataframe(frame, tmp_path / "events")
    assert csv.exists()
    loaded = load_dataframe(tmp_path / "events")
    assert len(loaded) == 2
    assert set(loaded["source_event_id"].astype(str)) == {"1001", "A-2"}


def test_loader_prefers_newer_csv_over_stale_parquet(tmp_path: Path, monkeypatch):
    base = tmp_path / "dataset"
    parquet = base.with_suffix(".parquet")
    csv = base.with_suffix(".csv")
    parquet.write_bytes(b"stale parquet placeholder")
    pd.DataFrame({"value": [2]}).to_csv(csv, index=False)

    import os
    os.utime(parquet, (1, 1))
    os.utime(csv, None)
    monkeypatch.setattr(pd, "read_parquet", lambda _: pd.DataFrame({"value": [1]}))

    loaded = load_dataframe(base)
    assert loaded.iloc[0]["value"] == 2
