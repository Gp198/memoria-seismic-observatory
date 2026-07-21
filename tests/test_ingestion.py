import json
import pandas as pd

from src.ingestion.ahead import normalise_ahead_payload
from src.ingestion.ipma import normalise_ipma_payload
from src.ingestion.isc import normalise_isc_frame


def test_ipma_parser_accepts_aliases():
    payload = {
        "data": [
            {
                "id": "x1",
                "time": "2026-07-20T10:20:30Z",
                "latitude": "36.5",
                "longitude": "-9.8",
                "depth": "20",
                "magnitud": "3.2",
                "local": "SW Faro",
            }
        ]
    }
    frame = normalise_ipma_payload(payload)
    assert len(frame) == 1
    assert frame.iloc[0]["source"] == "IPMA"
    assert frame.iloc[0]["magnitude_value"] == 3.2


def test_isc_parser():
    raw = pd.DataFrame(
        [
            {
                "eventid": "isc1",
                "time": "2020-01-01T00:00:00Z",
                "latitude": 38.5,
                "longitude": -9.2,
                "depth": 12,
                "magnitude": 3.4,
                "magnitudetype": "mb",
            }
        ]
    )
    frame = normalise_isc_frame(raw)
    assert len(frame) == 1
    assert frame.iloc[0]["magnitude_type"] == "mb"


def test_ahead_parser():
    payload = {
        "features": [
            {
                "properties": {
                    "EqID": "1755",
                    "Year": 1755,
                    "Mo": 11,
                    "Da": 1,
                    "Ho": 9,
                    "Mi": 40,
                    "Lat": 36.0,
                    "Lon": -10.0,
                    "Mw": 8.5,
                },
                "geometry": {"type": "Point", "coordinates": [-10.0, 36.0]},
            }
        ]
    }
    frame = normalise_ahead_payload(payload)
    assert len(frame) == 1
    assert frame.iloc[0]["source"] == "AHEAD"



def test_isc_fdsn_pipe_text_parser():
    from src.ingestion.isc import (
        normalise_isc_response,
        parse_isc_response_text,
    )

    text = (
        "#EventID|Time|Latitude|Longitude|Depth/Km|Author|Catalog|"
        "Contributor|ContributorID|MagType|Magnitude|MagAuthor|"
        "EventLocationName\n"
        "12345|2020-01-01T01:02:03.000|38.500|-9.200|12.0|ISC|"
        "ISC|ISC|12345|mb|3.4|ISC|PORTUGAL\n"
    )
    raw = parse_isc_response_text(text)
    assert list(raw.columns) == [
        "event_id",
        "time",
        "latitude",
        "longitude",
        "depth_km",
        "author",
        "catalog",
        "contributor",
        "contributor_id",
        "magnitude_type",
        "magnitude",
        "magnitude_author",
        "location",
    ]
    frame = normalise_isc_response(text)
    assert len(frame) == 1
    assert frame.iloc[0]["source"] == "ISC"
    assert frame.iloc[0]["source_event_id"] == "12345"
    assert frame.iloc[0]["magnitude_value"] == 3.4
    assert frame.iloc[0]["location_text"] == "PORTUGAL"


def test_isc_parser_rejects_unrecognised_success_body():
    import pytest

    from src.ingestion.isc import parse_isc_response_text

    with pytest.raises(ValueError):
        parse_isc_response_text("This is not an FDSN catalogue")


def test_isc_parser_accepts_header_only_no_data():
    from src.ingestion.isc import parse_isc_response_text

    text = (
        "#EventID|Time|Latitude|Longitude|Depth/Km|Author|Catalog|"
        "Contributor|ContributorID|MagType|Magnitude|MagAuthor|"
        "EventLocationName\n"
    )
    frame = parse_isc_response_text(text)
    assert frame.empty



def test_isc_month_chunks_and_future_clamp():
    from src.ingestion.isc import _date_chunks_months

    chunks = list(_date_chunks_months("2008-01-01", "2009-01-01", 3))
    assert len(chunks) == 4
    assert chunks[0][0].strftime("%Y-%m-%d") == "2008-01-01"
    assert chunks[0][1].strftime("%Y-%m-%d") == "2008-04-01"


def test_isc_adaptive_split_after_timeout(monkeypatch, tmp_path):
    import requests

    import src.ingestion.isc as isc

    response_text = (
        "#EventID|Time|Latitude|Longitude|Depth/Km|Author|Catalog|"
        "Contributor|ContributorID|MagType|Magnitude|MagAuthor|"
        "EventLocationName\n"
        "x|2008-01-15T00:00:00|38.0|-9.0|10|ISC|ISC|ISC|x|mb|2.0|ISC|PORTUGAL\n"
    )

    class Response:
        status_code = 200
        text = response_text
        url = "https://example.test"
        headers = {"Content-Type": "text/plain"}
        def raise_for_status(self):
            return None

    class Session:
        def get(self, url, params, **kwargs):
            start = pd.to_datetime(params["starttime"], utc=True)
            end = pd.to_datetime(params["endtime"], utc=True)
            if (end - start).days > 40:
                raise requests.exceptions.ReadTimeout("slow")
            return Response()

    import src.storage as storage

    class FakePaths:
        bronze = tmp_path / "bronze"
        def ensure(self):
            self.bronze.mkdir(parents=True, exist_ok=True)

    fake_paths = FakePaths()
    monkeypatch.setattr(isc, "PATHS", fake_paths)
    monkeypatch.setattr(storage, "PATHS", fake_paths)
    frame, manifest = isc.fetch_isc_events(
        "2008-01-01",
        "2008-04-01",
        session=Session(),
        chunk_months=3,
        min_chunk_days=7,
        max_retries=0,
        read_timeout=1,
    )
    assert len(frame) == 1
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert len(payload["successful_chunks"]) >= 2


def test_isc_resume_reads_completed_bronze(monkeypatch, tmp_path):
    import src.ingestion.isc as isc

    response_text = (
        "#EventID|Time|Latitude|Longitude|Depth/Km|Author|Catalog|"
        "Contributor|ContributorID|MagType|Magnitude|MagAuthor|"
        "EventLocationName\n"
        "x|2008-01-15T00:00:00|38.0|-9.0|10|ISC|ISC|ISC|x|mb|2.0|ISC|PORTUGAL\n"
    )

    class Response:
        status_code = 200
        text = response_text
        url = "https://example.test"
        headers = {"Content-Type": "text/plain"}
        def raise_for_status(self):
            return None

    class Session:
        calls = 0
        def get(self, url, params, **kwargs):
            self.calls += 1
            return Response()

    import src.storage as storage

    class FakePaths:
        bronze = tmp_path / "bronze"
        def ensure(self):
            self.bronze.mkdir(parents=True, exist_ok=True)

    fake_paths = FakePaths()
    monkeypatch.setattr(isc, "PATHS", fake_paths)
    monkeypatch.setattr(storage, "PATHS", fake_paths)
    first = Session()
    frame1, _ = isc.fetch_isc_events(
        "2008-01-01", "2008-02-01", session=first, chunk_months=1
    )
    second = Session()
    frame2, _ = isc.fetch_isc_events(
        "2008-01-01", "2008-02-01", session=second, chunk_months=1
    )
    assert len(frame1) == len(frame2) == 1
    assert first.calls == 1
    assert second.calls == 0
