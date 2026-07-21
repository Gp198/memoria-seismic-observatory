from __future__ import annotations

import json

import pandas as pd
import pytest

from src.assistant.context import build_assistant_context, context_to_text
from src.assistant.mistral_client import (
    MistralAssistantClient,
    MistralAssistantConfig,
    MistralAuthenticationError,
    MistralRateLimitError,
)
from src.assistant.prompts import build_messages


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def sample_context():
    events = pd.DataFrame(
        {
            "origin_time_utc": pd.to_datetime(
                ["2026-07-01", "2026-07-02"], utc=True
            ),
            "magnitude_comparable": [2.1, 4.2],
            "depth_km": [10.0, 20.0],
            "source": ["IPMA", "ISC"],
            "latitude": [38.0, 39.0],
            "longitude": [-9.0, -10.0],
        }
    )
    fingerprints = pd.DataFrame(
        {
            "window_end": pd.to_datetime(["2026-07-02"], utc=True),
            "window_start": pd.to_datetime(["2026-04-03"], utc=True),
            "window_days": [90],
            "event_count": [2],
            "comparable_event_count": [1],
            "maximum_magnitude": [4.2],
            "comparable_percentile_event_rate": [0.32],
            "comparison_epoch_label": ["Instrumental contemporâneo"],
            "comparison_magnitude_threshold": [1.5],
        }
    )
    return build_assistant_context(
        page="Visão geral",
        selected_domain="Margem Sudoeste Ibérica",
        catalogue_label="Completo",
        catalogue_mode="complete",
        magnitude_policy_label="Operacional · auditada",
        magnitude_policy="operational",
        selected_window=90,
        minimum_map_magnitude=1.5,
        domain_events=events,
        domain_fingerprints=fingerprints,
        validated_coverage=0.002,
        page_details={"activity_state": "Sem evidência robusta"},
        app_version="0.6.0",
    )


def test_context_contains_only_aggregate_summary():
    context = sample_context()
    text = context_to_text(context)
    assert "Margem Sudoeste Ibérica" in text
    assert '"event_count": 2' in text
    assert '"latitude"' not in text
    assert '"longitude"' not in text
    assert "MISTRAL_API_KEY" not in text


def test_prompt_includes_scientific_boundaries():
    messages = build_messages(
        question="Vai ocorrer um grande sismo?",
        context_text=context_to_text(sample_context()),
    )
    assert messages[0]["role"] == "system"
    assert "Nunca afirmes que um sismo é iminente" in messages[0]["content"]
    assert "CONTEXTO DO DASHBOARD" in messages[-1]["content"]


def test_mistral_client_success():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "model": "mistral-small-latest",
                    "choices": [
                        {"message": {"content": "O percentil é relativo."}}
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                    },
                },
            )
        ]
    )
    client = MistralAssistantClient(
        MistralAssistantConfig(api_key="test"),
        session=session,
        sleep_function=lambda _: None,
    )
    response = client.complete(
        question="Explica o percentil.",
        context_text=context_to_text(sample_context()),
    )
    assert response.text == "O percentil é relativo."
    assert response.total_tokens == 110
    assert session.calls[0][0].endswith("/chat/completions")
    sent = session.calls[0][1]["json"]
    assert sent["model"] == "mistral-small-latest"
    assert sent["safe_prompt"] is True


def test_mistral_client_authentication_error():
    client = MistralAssistantClient(
        MistralAssistantConfig(api_key="bad"),
        session=FakeSession([FakeResponse(401, {})]),
        sleep_function=lambda _: None,
    )
    with pytest.raises(MistralAuthenticationError):
        client.complete(question="Teste", context_text="{}")


def test_mistral_client_rate_limit_retries():
    session = FakeSession(
        [
            FakeResponse(429, {}, {"Retry-After": "0"}),
            FakeResponse(429, {}, {"Retry-After": "0"}),
        ]
    )
    client = MistralAssistantClient(
        MistralAssistantConfig(api_key="test", max_retries=1),
        session=session,
        sleep_function=lambda _: None,
    )
    with pytest.raises(MistralRateLimitError):
        client.complete(question="Teste", context_text="{}")
    assert len(session.calls) == 2


def test_context_text_is_valid_json_when_truncated():
    text = context_to_text({"large": "x" * 5000}, max_characters=500)
    parsed = json.loads(text)
    assert parsed["context_truncated"] is True
