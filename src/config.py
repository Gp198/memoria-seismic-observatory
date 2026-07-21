from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Paths:
    root: Path = PROJECT_ROOT
    data: Path = PROJECT_ROOT / "data"
    bronze: Path = PROJECT_ROOT / "data" / "bronze"
    silver: Path = PROJECT_ROOT / "data" / "silver"
    gold: Path = PROJECT_ROOT / "data" / "gold"
    sample: Path = PROJECT_ROOT / "data" / "sample"
    reports: Path = PROJECT_ROOT / "reports"
    config: Path = PROJECT_ROOT / "config"

    def ensure(self) -> None:
        for path in (
            self.data,
            self.bronze,
            self.silver,
            self.gold,
            self.sample,
            self.reports,
            self.config,
        ):
            path.mkdir(parents=True, exist_ok=True)


PATHS = Paths()


def load_settings() -> dict[str, Any]:
    path = PATHS.config / "settings.json"
    with path.open("r", encoding="utf-8") as handle:
        settings = json.load(handle)
    settings["request_timeout_seconds"] = int(
        os.getenv("MEMORIA_REQUEST_TIMEOUT", settings["request_timeout_seconds"])
    )
    settings["user_agent"] = os.getenv(
        "MEMORIA_USER_AGENT",
        "MEMORIA-Seismic-Observatory/0.1 research-prototype",
    )
    return settings
