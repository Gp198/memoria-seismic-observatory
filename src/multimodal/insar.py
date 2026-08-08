from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_insar_csv(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(file_path)
    if "date" in data:
        data["date"] = pd.to_datetime(data["date"], utc=True, errors="coerce")
    return data


def insar_anomaly_summary(data: pd.DataFrame) -> dict[str, object]:
    if data.empty:
        return {"available": False, "status": "Não disponível"}
    candidate = next((column for column in ["los_displacement_mm", "velocity_mm_year"] if column in data), None)
    if not candidate:
        return {"available": True, "status": "Sem variável suportada", "rows": len(data)}
    values = pd.to_numeric(data[candidate], errors="coerce").dropna()
    if len(values) < 10:
        return {"available": True, "status": "Amostra insuficiente", "rows": len(data)}
    current = float(values.iloc[-1]); q1=float(values.quantile(.25)); q3=float(values.quantile(.75)); iqr=max(q3-q1,1e-9)
    score = (current-float(values.median()))/iqr
    return {"available": True, "status": "Anómalo" if abs(score)>=2 else "Dentro da referência", "variable": candidate, "robust_iqr_score": float(score), "rows": len(data)}
