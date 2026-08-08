import pandas as pd

from src.multimodal.gnss import gnss_anomaly_summary
from src.multimodal.insar import insar_anomaly_summary
from src.evidence.graph import build_evidence_graph
from src.anomalies.engine import AnomalyAssessment, AnomalyComponent


def test_multimodal_empty_is_not_available():
    assert gnss_anomaly_summary(pd.DataFrame())["available"] is False
    assert insar_anomaly_summary(pd.DataFrame())["available"] is False


def test_evidence_graph_has_state_and_detector():
    anomaly=AnomalyAssessment(70,"Moderada",True,"test",3,3,5,(AnomalyComponent("X",80,True,"detail"),),100,.9)
    nodes,edges=build_evidence_graph(anomaly)
    assert "state" in set(nodes["node_id"])
    assert len(edges)==1
