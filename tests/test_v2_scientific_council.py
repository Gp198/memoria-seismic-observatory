import json

import pytest

from src.agents.scientific_council import (
    AGENT_ROLES,
    AGENT_TOKEN_BUDGETS,
    CHAIR_TOKEN_BUDGET,
    estimate_council_budget,
    run_scientific_council,
)
from src.assistant.mistral_client import MistralAssistantResponse


AGENT_OK = """VEREDITO
Resultado experimental e research-only.

EVIDÊNCIA
Apenas a evidência fornecida foi considerada.

FRAGILIDADES
A interpretação tectónica não está confirmada.

RECOMENDAÇÃO
Continuar validação e testes de robustez.
"""

CHAIR_OK = """CONSENSO
A evidência é experimental.

DISCORDÂNCIAS
Não existem discordâncias adicionais a registar neste teste.

FORÇA DA EVIDÊNCIA
Limitada.

DECISÃO DE USO
Research-only.

PRÓXIMOS TESTES
Repetir a avaliação com mais evidência independente.
"""


def evidence(**manifest_overrides):
    manifest = {
        "evidence_date_utc": "2026-08-07T20:00:00+00:00",
        "loaded_catalogue_sources": ["IPMA", "ISC", "AHEAD"],
        "fault_context_loaded": False,
        "fault_names_loaded": [],
        "gnss_context_loaded": False,
        "insar_context_loaded": False,
        "model_arena_available": False,
        "external_knowledge_allowed": False,
    }
    manifest.update(manifest_overrides)
    return json.dumps({"grounding_manifest": manifest, "anomaly": {"score": 53.66}}, ensure_ascii=False)


class QueueFakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete_with_system(self, *, system_prompt, question, context_text, max_tokens=None):
        self.calls.append((system_prompt, question, context_text, max_tokens))
        if not self.responses:
            raise AssertionError("No fake response left")
        item = self.responses.pop(0)
        if isinstance(item, MistralAssistantResponse):
            return item
        return MistralAssistantResponse(text=item, model="fake", finish_reason="stop")


def test_scientific_council_runs_agents_and_chair():
    client = QueueFakeClient([AGENT_OK, AGENT_OK, CHAIR_OK])
    result = run_scientific_council(client, evidence(), agents=["Seismologist", "Skeptic"])
    assert len(result.reviews) == 2
    assert result.synthesis.agent == "Chair"
    assert result.evidence_date_utc == "2026-08-07T20:00:00+00:00"
    assert all(review.grounding_passed for review in result.reviews)
    assert result.synthesis.grounding_passed
    assert "Skeptic" in AGENT_ROLES


def test_role_specific_token_budgets_and_compact_context_are_used():
    client = QueueFakeClient([AGENT_OK, AGENT_OK, CHAIR_OK])
    run_scientific_council(client, evidence(), agents=["Seismologist", "Model Reviewer"])
    assert client.calls[0][3] == AGENT_TOKEN_BUDGETS["Seismologist"]
    assert client.calls[1][3] == AGENT_TOKEN_BUDGETS["Model Reviewer"]
    assert client.calls[2][3] == CHAIR_TOKEN_BUDGET
    # The role context remains JSON and explicitly marks its restricted scope.
    assert "evidence_scope" in client.calls[0][2]
    assert "evidence_scope" in client.calls[1][2]


def test_budget_estimate_matches_selected_agents():
    budget = estimate_council_budget(["Statistician", "Skeptic"])
    assert budget["normal_requests"] == 3
    assert budget["maximum_requests"] == 6
    assert budget["normal_completion_ceiling"] == AGENT_TOKEN_BUDGETS["Statistician"] + AGENT_TOKEN_BUDGETS["Skeptic"] + CHAIR_TOKEN_BUDGET


def test_usage_is_aggregated_across_agents_and_chair():
    agent = MistralAssistantResponse(
        text=AGENT_OK,
        model="fake",
        prompt_tokens=100,
        completion_tokens=40,
        total_tokens=140,
        finish_reason="stop",
    )
    chair = MistralAssistantResponse(
        text=CHAIR_OK,
        model="fake",
        prompt_tokens=80,
        completion_tokens=30,
        total_tokens=110,
        finish_reason="stop",
    )
    client = QueueFakeClient([agent, chair])
    result = run_scientific_council(client, evidence(), agents=["Statistician"])
    assert result.api_requests == 2
    assert result.prompt_tokens == 180
    assert result.completion_tokens == 70
    assert result.total_tokens == 250


def test_unsupported_external_entity_forces_single_retry():
    hallucinated = AGENT_OK.replace(
        "Apenas a evidência fornecida foi considerada.",
        "O catálogo EMSC confirma o sinal observado.",
    )
    client = QueueFakeClient([hallucinated, AGENT_OK, CHAIR_OK])
    result = run_scientific_council(client, evidence(), agents=["Seismologist"])
    review = result.reviews[0]
    assert review.attempts == 2
    assert review.grounding_passed
    assert "EMSC" not in review.text
    assert len(client.calls) == 3


def test_named_fault_claim_is_rejected_when_fault_context_is_not_loaded():
    hallucinated = AGENT_OK.replace(
        "Apenas a evidência fornecida foi considerada.",
        "A Falha de Marquês de Pombal explica a migração observada.",
    )
    client = QueueFakeClient([hallucinated, AGENT_OK, CHAIR_OK])
    result = run_scientific_council(client, evidence(fault_context_loaded=False), agents=["Seismologist"])
    assert result.reviews[0].attempts == 2
    assert "Marquês de Pombal" not in result.reviews[0].text


def test_gnss_cannot_be_used_as_observed_evidence_when_not_loaded():
    hallucinated = AGENT_OK.replace(
        "Apenas a evidência fornecida foi considerada.",
        "GNSS confirma deformação crustal associada ao sinal.",
    )
    client = QueueFakeClient([hallucinated, AGENT_OK, CHAIR_OK])
    result = run_scientific_council(client, evidence(gnss_context_loaded=False), agents=["Statistician"])
    assert result.reviews[0].attempts == 2
    assert result.reviews[0].grounding_passed


def test_token_limited_agent_response_is_retried():
    truncated = MistralAssistantResponse(
        text="VEREDITO\nExperimental\n\nEVIDÊNCIA\nTexto incompleto",
        model="fake",
        finish_reason="length",
    )
    client = QueueFakeClient([truncated, AGENT_OK, CHAIR_OK])
    result = run_scientific_council(client, evidence(), agents=["Model Reviewer"])
    assert result.reviews[0].attempts == 2
    assert result.reviews[0].grounding_passed
    assert "RECOMENDAÇÃO" in result.reviews[0].text


def test_chair_data_placeholder_is_replaced_with_real_evidence_date():
    chair_with_placeholder = CHAIR_OK.replace(
        "A evidência é experimental.",
        "Data: [Data atual]. A evidência é experimental.",
    )
    client = QueueFakeClient([AGENT_OK, chair_with_placeholder])
    result = run_scientific_council(client, evidence(), agents=["Skeptic"])
    assert "[Data atual]" not in result.synthesis.text
    assert "2026-08-07T20:00:00+00:00" in result.synthesis.text
    assert result.synthesis.grounding_passed


def test_second_grounding_failure_is_withheld_behind_safe_fallback():
    bad = AGENT_OK.replace(
        "Apenas a evidência fornecida foi considerada.",
        "O catálogo EMSC e a Horseshoe confirmam a interpretação.",
    )
    client = QueueFakeClient([bad, bad, CHAIR_OK])
    result = run_scientific_council(client, evidence(), agents=["Data Quality Auditor"])
    review = result.reviews[0]
    assert review.attempts == 2
    assert not review.grounding_passed
    assert "Revisão automática não publicada" in review.text
    assert "EMSC" not in review.text


def test_unknown_agent_is_rejected():
    with pytest.raises(ValueError):
        run_scientific_council(QueueFakeClient([]), evidence(), agents=["Oracle"])


def test_gnss_future_work_mention_is_allowed_when_not_loaded():
    safe = AGENT_OK.replace(
        "Continuar validação e testes de robustez.",
        "Seria útil obter GNSS e InSAR como evidência independente em trabalho futuro; estes dados não estão carregados.",
    )
    client = QueueFakeClient([safe, CHAIR_OK])
    result = run_scientific_council(client, evidence(gnss_context_loaded=False, insar_context_loaded=False), agents=["Seismologist"])
    assert result.reviews[0].grounding_passed
    assert result.reviews[0].attempts == 1
    assert len(client.calls) == 2


def test_gnss_absence_can_be_stated_as_limitation_without_retry():
    safe = AGENT_OK.replace(
        "A interpretação tectónica não está confirmada.",
        "Sem dados GNSS carregados, a interpretação tectónica não é avaliável com evidência geodésica independente.",
    )
    client = QueueFakeClient([safe, CHAIR_OK])
    result = run_scientific_council(client, evidence(gnss_context_loaded=False), agents=["Statistician"])
    assert result.reviews[0].grounding_passed
    assert result.reviews[0].attempts == 1


def test_chair_llm_is_skipped_when_no_reviewer_is_grounded():
    bad = AGENT_OK.replace(
        "Apenas a evidência fornecida foi considerada.",
        "GNSS confirma deformação e o catálogo EMSC confirma o sinal.",
    )
    client = QueueFakeClient([bad, bad])
    result = run_scientific_council(client, evidence(), agents=["Seismologist"])
    assert not result.reviews[0].grounding_passed
    assert result.synthesis.model == "local-deterministic"
    assert result.synthesis.api_requests == 0
    assert result.api_requests == 2
    assert len(client.calls) == 2
