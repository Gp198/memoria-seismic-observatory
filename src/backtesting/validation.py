from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, precision_recall_curve


@dataclass
class BacktestValidation:
    scores: pd.DataFrame
    metrics: pd.DataFrame
    calibration: pd.DataFrame
    classification: pd.DataFrame
    precision_recall: pd.DataFrame
    sample_count: int
    positive_count: int
    calibrated_count: int
    calibrated_positive_count: int
    calibration_status: str
    calibration_message: str


def add_expanding_isotonic_calibration(scores: pd.DataFrame, minimum_history: int = 30) -> pd.DataFrame:
    result = scores.copy().sort_values("cutoff").reset_index(drop=True)
    result["analogue_calibrated_probability"] = np.nan
    for index in range(len(result)):
        history = result.iloc[:index].dropna(subset=["analogue_probability", "observed_outcome"])
        if len(history) < minimum_history:
            continue
        outcomes = history["observed_outcome"].astype(float)
        probabilities = pd.to_numeric(history["analogue_probability"], errors="coerce")
        valid = probabilities.notna() & outcomes.notna()
        probabilities = probabilities.loc[valid]
        outcomes = outcomes.loc[valid]
        if outcomes.nunique() < 2 or probabilities.nunique() < 3:
            continue
        calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        calibrator.fit(probabilities.to_numpy(float), outcomes.to_numpy(float))
        raw = float(result.loc[index, "analogue_probability"])
        result.loc[index, "analogue_calibrated_probability"] = float(calibrator.predict([raw])[0])
    observed = result["observed_outcome"].astype(float)
    result["brier_analogue_calibrated"] = (result["analogue_calibrated_probability"] - observed) ** 2
    return result


def brier_skill_score(model_brier: float, reference_brier: float) -> float:
    if not np.isfinite(model_brier) or not np.isfinite(reference_brier) or reference_brier <= 0:
        return np.nan
    return float(1.0 - model_brier / reference_brier)


def _wilson_interval(positive: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    if total <= 0:
        return np.nan, np.nan
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    p = positive / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * np.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return float(max(0.0, centre - margin)), float(min(1.0, centre + margin))


def _calibration_table(scores: pd.DataFrame, columns: dict[str, str], bins: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    for label, column in columns.items():
        data = scores[[column, "observed_outcome"]].dropna().copy()
        if data.empty:
            continue
        data["bin"] = pd.cut(data[column].clip(0.0, 1.0), bins=boundaries, include_lowest=True, duplicates="drop")
        for interval, group in data.groupby("bin", observed=False):
            if group.empty:
                continue
            positives = int(group["observed_outcome"].astype(bool).sum())
            lower, upper = _wilson_interval(positives, len(group))
            rows.append({
                "Modelo": label,
                "Intervalo": str(interval),
                "Probabilidade média": float(group[column].mean()),
                "Frequência observada": float(positives / len(group)),
                "IC 95% inferior": lower,
                "IC 95% superior": upper,
                "Cortes": int(len(group)),
                "Eventos observados": positives,
            })
    return pd.DataFrame(rows)


def _classification_metrics(scores: pd.DataFrame, columns: dict[str, str], decision_thresholds: tuple[float, ...]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    actual = scores["observed_outcome"].astype(bool)
    for label, column in columns.items():
        probability = pd.to_numeric(scores[column], errors="coerce")
        valid = probability.notna() & actual.notna()
        if not valid.any():
            continue
        observed = actual.loc[valid]
        for threshold in decision_thresholds:
            predicted = probability.loc[valid] >= float(threshold)
            tp = int((predicted & observed).sum()); fp = int((predicted & ~observed).sum())
            tn = int((~predicted & ~observed).sum()); fn = int((~predicted & observed).sum())
            precision = tp / (tp + fp) if tp + fp else np.nan
            recall = tp / (tp + fn) if tp + fn else np.nan
            false_alarm_rate = fp / (fp + tn) if fp + tn else np.nan
            f1 = 2 * precision * recall / (precision + recall) if np.isfinite(precision) and np.isfinite(recall) and precision + recall else np.nan
            rows.append({
                "Modelo": label,
                "Limiar de decisão": float(threshold),
                "Verdadeiros positivos": tp,
                "Falsos positivos": fp,
                "Verdadeiros negativos": tn,
                "Falsos negativos": fn,
                "Precisão": precision,
                "Recall": recall,
                "F1": f1,
                "Taxa de falsos alarmes": false_alarm_rate,
            })
    return pd.DataFrame(rows)


def _precision_recall_table(scores: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, column in columns.items():
        data = scores[[column, "observed_outcome"]].dropna()
        if data.empty or data["observed_outcome"].astype(int).nunique() < 2:
            continue
        y = data["observed_outcome"].astype(int).to_numpy()
        probability = data[column].astype(float).to_numpy()
        precision, recall, thresholds = precision_recall_curve(y, probability)
        average_precision = float(average_precision_score(y, probability))
        for index in range(len(precision)):
            threshold = float(thresholds[index]) if index < len(thresholds) else np.nan
            rows.append({
                "Modelo": label,
                "Recall": float(recall[index]),
                "Precisão": float(precision[index]),
                "Limiar": threshold,
                "Average precision": average_precision,
                "Cortes": int(len(data)),
                "Eventos observados": int(y.sum()),
            })
    return pd.DataFrame(rows)


def expected_calibration_error(scores: pd.DataFrame, probability_column: str, bins: int = 10) -> float:
    data = scores[[probability_column, "observed_outcome"]].dropna().copy()
    if data.empty:
        return np.nan
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    data["bin"] = pd.cut(data[probability_column].clip(0.0, 1.0), bins=boundaries, include_lowest=True, duplicates="drop")
    total = len(data); error = 0.0
    for _, group in data.groupby("bin", observed=False):
        if group.empty: continue
        predicted = float(group[probability_column].mean())
        observed = float(group["observed_outcome"].astype(float).mean())
        error += len(group) / total * abs(predicted - observed)
    return float(error)


def _calibration_status(calibrated: pd.DataFrame, minimum_cuts: int = 30, minimum_positives: int = 5) -> tuple[str, str, int, int]:
    subset = calibrated.dropna(subset=["analogue_calibrated_probability", "observed_outcome"])
    cuts = int(len(subset)); positives = int(subset["observed_outcome"].astype(bool).sum())
    if cuts == 0:
        return "unavailable", "Calibração indisponível: não existem cortes elegíveis.", cuts, positives
    if cuts < minimum_cuts or positives < minimum_positives:
        return (
            "experimental",
            f"Calibração experimental: {cuts} cortes e {positives} positivos; recomenda-se pelo menos {minimum_cuts} cortes e {minimum_positives} positivos.",
            cuts,
            positives,
        )
    return "adequate", f"Calibração com amostra mínima atingida: {cuts} cortes e {positives} positivos.", cuts, positives


def summarise_backtest_grid(scores: pd.DataFrame, calibration_bins: int = 5, decision_thresholds: tuple[float, ...] = (0.005, 0.01, 0.02, 0.05, 0.10), minimum_calibration_history: int = 30) -> pd.DataFrame:
    if scores.empty: return pd.DataFrame()
    rows=[]
    group_columns=[c for c in ["catalogue_mode","magnitude_policy","threshold_magnitude","horizon_days"] if c in scores.columns]
    for keys, group in scores.groupby(group_columns, dropna=False):
        summary=summarise_backtest(group, calibration_bins, decision_thresholds, minimum_calibration_history)
        key_values=keys if isinstance(keys,tuple) else (keys,)
        dimensions=dict(zip(group_columns,key_values))
        for _, metric in summary.metrics.iterrows():
            rows.append({**dimensions, **metric.to_dict(), "Eventos observados":summary.positive_count, "Cortes totais":summary.sample_count, "Cortes calibrados":summary.calibrated_count, "Estado da calibração":summary.calibration_status})
    return pd.DataFrame(rows)


def summarise_backtest(scores: pd.DataFrame, calibration_bins: int = 5, decision_thresholds: tuple[float, ...] = (0.005, 0.01, 0.02, 0.05, 0.10), minimum_calibration_history: int = 30) -> BacktestValidation:
    calibrated=add_expanding_isotonic_calibration(scores, minimum_calibration_history)
    observed=calibrated["observed_outcome"].astype(float)
    model_columns={"Famílias — score bruto":"analogue_probability","Famílias — calibrado":"analogue_calibrated_probability","Frequência empírica":"historical_rate_probability","Poisson":"poisson_probability"}
    brier_columns={"Famílias — score bruto":"brier_analogue","Famílias — calibrado":"brier_analogue_calibrated","Frequência empírica":"brier_historical","Poisson":"brier_poisson"}
    metric_rows=[]
    for label,column in model_columns.items():
        valid=calibrated[[column,"observed_outcome"]].dropna()
        if valid.empty: continue
        mean_probability=float(valid[column].mean()); observed_rate=float(valid["observed_outcome"].astype(float).mean())
        mean_brier=float(pd.to_numeric(calibrated.loc[valid.index,brier_columns[label]],errors="coerce").mean())
        empirical_brier=float(pd.to_numeric(calibrated.loc[valid.index,"brier_historical"],errors="coerce").mean())
        poisson_brier=float(pd.to_numeric(calibrated.loc[valid.index,"brier_poisson"],errors="coerce").mean())
        y=valid["observed_outcome"].astype(int)
        average_precision=float(average_precision_score(y,valid[column])) if y.nunique()>1 else np.nan
        metric_rows.append({"Modelo":label,"Cortes válidos":int(len(valid)),"Probabilidade média":mean_probability,"Frequência observada":observed_rate,"Brier médio":mean_brier,"BSS vs. empírico":brier_skill_score(mean_brier,empirical_brier),"BSS vs. Poisson":brier_skill_score(mean_brier,poisson_brier),"Erro de calibração esperado":expected_calibration_error(calibrated.loc[valid.index],column,bins=calibration_bins),"Average precision":average_precision})
    calibration=_calibration_table(calibrated,model_columns,calibration_bins)
    classification=_classification_metrics(calibrated,model_columns,decision_thresholds)
    pr=_precision_recall_table(calibrated,model_columns)
    status,message,calibrated_count,calibrated_positive_count=_calibration_status(calibrated)
    return BacktestValidation(calibrated,pd.DataFrame(metric_rows),calibration,classification,pr,int(len(calibrated)),int(observed.sum()),calibrated_count,calibrated_positive_count,status,message)
