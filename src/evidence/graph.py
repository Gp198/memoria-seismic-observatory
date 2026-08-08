from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    label: str
    category: str
    value: str
    confidence: str


@dataclass(frozen=True)
class EvidenceEdge:
    source: str
    target: str
    relation: str


def build_evidence_graph(
    anomaly: Any,
    b_value: Any = None,
    migration: Any = None,
    gnss: dict[str, object] | None = None,
    insar: dict[str, object] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = [EvidenceNode("state", "Estado atual", "conclusion", f"{getattr(anomaly,'level','—')} · {getattr(anomaly,'score',0):.0f}/100", "experimental")]
    edges = []
    for index, component in enumerate(getattr(anomaly, "components", ())):
        node_id = f"anomaly_{index}"
        nodes.append(EvidenceNode(node_id, component.name, "detector", f"{component.score:.1f}/100", "triggered" if component.triggered else "not-triggered"))
        edges.append(EvidenceEdge(node_id, "state", "supports" if component.triggered else "context"))
    if b_value is not None and getattr(b_value, "b_value", None) is not None:
        nodes.append(EvidenceNode("bvalue", "Gutenberg–Richter b", "seismology", f"{b_value.b_value:.2f} ± {b_value.sigma or 0:.2f}", "methodological"))
        edges.append(EvidenceEdge("bvalue", "state", "context"))
    if migration is not None and getattr(migration, "sufficient_data", False):
        nodes.append(EvidenceNode("migration", "Migração epicentral", "seismology", f"{migration.distance_km:.1f} km · {migration.bearing_degrees:.0f}°", "experimental"))
        edges.append(EvidenceEdge("migration", "state", "context"))
    for key, payload in [("gnss", gnss), ("insar", insar)]:
        if payload and payload.get("available"):
            nodes.append(EvidenceNode(key, key.upper(), "geophysics", str(payload.get("status")), "external"))
            edges.append(EvidenceEdge(key, "state", "multimodal-context"))
    return pd.DataFrame([asdict(node) for node in nodes]), pd.DataFrame([asdict(edge) for edge in edges])
