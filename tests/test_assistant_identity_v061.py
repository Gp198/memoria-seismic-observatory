from __future__ import annotations

import pandas as pd

from src.assistant.context import build_assistant_context, context_to_text
from src.assistant.identity import (
    PROJECT_IDENTITY_ANSWER,
    answer_identity_question,
    contains_false_ipma_attribution,
    enforce_identity_guard,
)
from src.assistant.mistral_client import MistralAssistantClient, MistralAssistantConfig
from src.assistant.prompts import build_messages


class NoCallSession:
    def post(self, *args, **kwargs):
        raise AssertionError("A API não deve ser chamada para perguntas de identidade.")


def _context():
    events = pd.DataFrame(
        {
            "origin_time_utc": pd.to_datetime(["2026-07-01"], utc=True),
            "magnitude_comparable": [2.1],
            "source": ["IPMA"],
        }
    )
    fingerprints = pd.DataFrame(
        {
            "window_end": pd.to_datetime(["2026-07-01"], utc=True),
            "window_start": pd.to_datetime(["2026-04-03"], utc=True),
            "window_days": [90],
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
        app_version="0.6.1",
    )


def test_context_has_authoritative_identity():
    text = context_to_text(_context())
    assert '"creator": "Gonçalo Pedro"' in text
    assert "não é um projeto, produto, iniciativa ou serviço oficial" in text


def test_system_prompt_has_non_negotiable_identity():
    messages = build_messages(question="Quem criou o MEMÓRIA?", context_text="{}")
    system = messages[0]["content"]
    assert "criado e é desenvolvido por Gonçalo Pedro" in system
    assert "NÃO é um projeto, produto, iniciativa ou serviço oficial do IPMA" in system


def test_identity_question_is_answered_locally_without_api():
    client = MistralAssistantClient(
        MistralAssistantConfig(api_key="test"), session=NoCallSession()
    )
    response = client.complete(
        question="O MEMÓRIA é um projeto do IPMA e quem o criou?",
        context_text="{}",
    )
    assert response.text == PROJECT_IDENTITY_ANSWER
    assert response.model == "memoria-local-identity-v0.6.1"


def test_identity_intent_detection():
    assert answer_identity_question("Quem desenvolveu o projeto MEMÓRIA?")
    assert answer_identity_question("Qual é a relação do MEMÓRIA com o IPMA?")
    assert answer_identity_question("Is this an IPMA project?")
    assert answer_identity_question("O que significa o percentil?") is None


def test_false_attribution_guard():
    false_text = "O MEMÓRIA é um projeto experimental do IPMA criado pela sua equipa."
    assert contains_false_ipma_attribution(false_text)
    corrected = enforce_identity_guard(false_text)
    assert "criado e é desenvolvido por Gonçalo Pedro" in corrected
    assert "não é um projeto" in corrected


def test_correct_negated_statement_is_not_replaced():
    correct = (
        "O MEMÓRIA não é um projeto do IPMA; foi criado por Gonçalo Pedro. "
        "O IPMA é uma fonte de dados."
    )
    assert not contains_false_ipma_attribution(correct)
    assert enforce_identity_guard(correct) == correct
