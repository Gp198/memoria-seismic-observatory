from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def load_gnss_csv(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(file_path)
    if "date" in data:
        data["date"] = pd.to_datetime(data["date"], utc=True, errors="coerce")
    return data


def gnss_anomaly_summary(data: pd.DataFrame) -> dict[str, object]:
    if data.empty:
        return {"available": False, "status": "Não disponível"}
    candidate = next((column for column in ["strain", "velocity_mm_year", "displacement_mm"] if column in data), None)
    if not candidate:
        return {"available": True, "status": "Sem variável suportada", "rows": len(data)}
    values = pd.to_numeric(data[candidate], errors="coerce").dropna()
    if len(values) < 10:
        return {"available": True, "status": "Amostra insuficiente", "rows": len(data)}
    median = float(values.median()); mad = float((values-median).abs().median())
    current = float(values.iloc[-1]); scale = max(1.4826*mad, float(values.std()), 1e-9)
    z = (current-median)/scale
    return {"available": True, "status": "Anómalo" if abs(z)>=3 else "Dentro da referência", "variable": candidate, "robust_z": float(z), "rows": len(data)}
