import pandas as pd

from src.models.arena import summarise_global_leaderboard


def test_global_leaderboard_uses_scenario_ranks_and_counts_wins():
    grid = pd.DataFrame([
        {"Magnitude-alvo": 4.0, "Horizonte": 30, "Fingerprint": 90, "Modelo": "Poisson", "Cortes": 100, "Eventos observados": 20, "Brier": 0.20, "BSS vs Poisson": 0.0, "Average Precision": 0.30},
        {"Magnitude-alvo": 4.0, "Horizonte": 30, "Fingerprint": 90, "Modelo": "ETAS", "Cortes": 100, "Eventos observados": 20, "Brier": 0.18, "BSS vs Poisson": 0.10, "Average Precision": 0.35},
        {"Magnitude-alvo": 4.5, "Horizonte": 90, "Fingerprint": 90, "Modelo": "Poisson", "Cortes": 90, "Eventos observados": 8, "Brier": 0.10, "BSS vs Poisson": 0.0, "Average Precision": 0.20},
        {"Magnitude-alvo": 4.5, "Horizonte": 90, "Fingerprint": 90, "Modelo": "ETAS", "Cortes": 90, "Eventos observados": 8, "Brier": 0.09, "BSS vs Poisson": 0.10, "Average Precision": 0.25},
    ])
    result = summarise_global_leaderboard(grid)
    assert list(result["Modelo"])[0] == "ETAS"
    etas = result.loc[result["Modelo"].eq("ETAS")].iloc[0]
    assert etas["Vitórias Brier"] == 2
    assert etas["Rank Brier médio"] == 1.0
    assert etas["Taxa de skill > Poisson"] == 1.0


def test_global_leaderboard_empty_input_is_safe():
    assert summarise_global_leaderboard(pd.DataFrame()).empty
