from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from src.assistant.mistral_client import MistralAssistantClient, MistralAssistantResponse


AGENT_ROLES = {
    "Seismologist": "Avalia interpretação sismológica, b-value, clustering, migração e plausibilidade tectónica. Não faz previsões.",
    "Statistician": "Audita amostra, incerteza, autocorrelação, calibração, métricas e significância. Procura conclusões excessivas.",
    "Data Quality Auditor": "Audita proveniência, completude, magnitudes, declustering, missingness e mudanças de fontes.",
    "Model Reviewer": "Avalia leakage, baselines, backtesting, overfitting, skill e comparabilidade entre modelos.",
    "Skeptic": "Tenta falsificar a conclusão: procura explicações alternativas, sensibilidade e condições em que o sinal desaparece.",
}

# Completion-token ceilings are deliberately role-specific. They are maxima, not reservations.
AGENT_TOKEN_BUDGETS = {
    "Seismologist": 750,
    "Statistician": 700,
    "Data Quality Auditor": 650,
    "Model Reviewer": 750,
    "Skeptic": 750,
}
CHAIR_TOKEN_BUDGET = 900
RETRY_TOKEN_BONUS = 150

AGENT_HEADINGS = ("VEREDITO", "EVIDÊNCIA", "FRAGILIDADES", "RECOMENDAÇÃO")
CHAIR_HEADINGS = ("CONSENSO", "DISCORDÂNCIAS", "FORÇA DA EVIDÊNCIA", "DECISÃO DE USO", "PRÓXIMOS TESTES")

# High-risk named external entities commonly hallucinated in early v2.0 Council tests.
# They are allowed only when the exact name is present in the evidence package.
HIGH_RISK_NAMED_ENTITIES = (
    "EMSC",
    "USGS",
    "IGN",
    "Falha de Marquês de Pombal",
    "Marquês de Pombal Fault",
    "Horseshoe Fault",
    "Horseshoe",
    "Gorringe",
    "Glória Fault",
    "Gloria Fault",
)

COMMON_EVIDENCE_KEYS = (
    "project",
    "domain",
    "catalogue_mode",
    "magnitude_policy",
    "grounding_manifest",
)
ROLE_EVIDENCE_KEYS = {
    "Seismologist": ("anomaly", "b_value", "migration", "multimodal_context", "seismic_regime"),
    "Statistician": ("anomaly", "b_value", "migration", "model_arena", "validation", "uncertainty"),
    "Data Quality Auditor": (
        "anomaly",
        "quality",
        "catalogue_quality",
        "magnitude_quality",
        "declustering",
        "multimodal_context",
    ),
    "Model Reviewer": ("anomaly", "model_arena", "validation", "uncertainty"),
    "Skeptic": (
        "anomaly",
        "b_value",
        "migration",
        "model_arena",
        "multimodal_context",
        "validation",
        "uncertainty",
    ),
}


@dataclass(frozen=True)
class CouncilReview:
    agent: str
    text: str
    model: str
    grounding_passed: bool = True
    grounding_issues: tuple[str, ...] = tuple()
    attempts: int = 1
    finish_reason: str | None = None
    api_requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class CouncilResult:
    reviews: tuple[CouncilReview, ...]
    synthesis: CouncilReview
    evidence_date_utc: str | None = None

    @property
    def api_requests(self) -> int:
        return sum(review.api_requests for review in self.reviews) + self.synthesis.api_requests

    @property
    def prompt_tokens(self) -> int:
        return sum(review.prompt_tokens for review in self.reviews) + self.synthesis.prompt_tokens

    @property
    def completion_tokens(self) -> int:
        return sum(review.completion_tokens for review in self.reviews) + self.synthesis.completion_tokens

    @property
    def total_tokens(self) -> int:
        explicit = sum(review.total_tokens for review in self.reviews) + self.synthesis.total_tokens
        return explicit if explicit else self.prompt_tokens + self.completion_tokens


def estimate_council_budget(agents: Iterable[str] | None = None) -> dict[str, int]:
    selected = list(agents or AGENT_ROLES.keys())
    unknown = [role for role in selected if role not in AGENT_ROLES]
    if unknown:
        raise ValueError(f"Agentes desconhecidos: {', '.join(unknown)}")
    normal_completion = sum(AGENT_TOKEN_BUDGETS[role] for role in selected) + CHAIR_TOKEN_BUDGET
    retry_completion = sum(AGENT_TOKEN_BUDGETS[role] + RETRY_TOKEN_BONUS for role in selected)
    retry_completion += CHAIR_TOKEN_BUDGET + RETRY_TOKEN_BONUS
    return {
        "normal_requests": len(selected) + 1,
        "maximum_requests": (len(selected) + 1) * 2,
        "normal_completion_ceiling": normal_completion,
        "retry_completion_ceiling": normal_completion + retry_completion,
    }


def _load_evidence(evidence_context: str) -> dict[str, object]:
    try:
        payload = json.loads(evidence_context)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _grounding_manifest(evidence_context: str) -> dict[str, object]:
    payload = _load_evidence(evidence_context)
    manifest = payload.get("grounding_manifest")
    return manifest if isinstance(manifest, dict) else {}


def _evidence_date(evidence_context: str) -> str | None:
    manifest = _grounding_manifest(evidence_context)
    value = manifest.get("evidence_date_utc")
    return str(value) if value else None


def _compact_value(value: object, *, list_limit: int = 12, depth: int = 0) -> object:
    """Keep scientific evidence machine-readable while avoiding repeated oversized prompts."""
    if depth >= 5:
        return str(value)[:500]
    if isinstance(value, dict):
        return {
            str(key): _compact_value(item, list_limit=list_limit, depth=depth + 1)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        trimmed = value[:list_limit]
        result = [_compact_value(item, list_limit=list_limit, depth=depth + 1) for item in trimmed]
        if len(value) > list_limit:
            result.append({"_omitted_items": len(value) - list_limit})
        return result
    if isinstance(value, tuple):
        return _compact_value(list(value), list_limit=list_limit, depth=depth)
    if isinstance(value, str) and len(value) > 1200:
        return value[:1200] + "…"
    return value


def _compact_evidence_for_role(evidence_context: str, role: str) -> str:
    payload = _load_evidence(evidence_context)
    if not payload:
        return evidence_context[:16000]
    selected: dict[str, object] = {}
    for key in (*COMMON_EVIDENCE_KEYS, *ROLE_EVIDENCE_KEYS.get(role, ())):
        if key in payload:
            selected[key] = _compact_value(payload[key])
    selected["evidence_scope"] = f"Pacote mínimo especializado para {role}; campos omitidos não devem ser inferidos."
    return json.dumps(selected, ensure_ascii=False, separators=(",", ":"), default=str)


def _compact_chair_evidence(evidence_context: str) -> str:
    payload = _load_evidence(evidence_context)
    if not payload:
        return evidence_context[:12000]
    selected: dict[str, object] = {}
    for key in (*COMMON_EVIDENCE_KEYS, "anomaly", "b_value", "migration", "model_arena", "multimodal_context"):
        if key in payload:
            selected[key] = _compact_value(payload[key], list_limit=8)
    selected["evidence_scope"] = "Resumo determinístico para o Chair; a evidência detalhada permanece no dashboard."
    return json.dumps(selected, ensure_ascii=False, separators=(",", ":"), default=str)


def _agent_system(role: str, mission: str) -> str:
    return f"""És o agente {role} do MEMÓRIA Scientific Council. {mission}
O MEMÓRIA é um projeto experimental independente criado por Gonçalo Pedro e não é um produto oficial do IPMA.

POLÍTICA DE GROUNDING OBRIGATÓRIA:
- Usa exclusivamente factos, métricas, entidades e relações presentes em EVIDÊNCIA MEMÓRIA.
- Não uses conhecimento externo para completar lacunas, mesmo que o conheças.
- Não nomes catálogos, instituições, falhas, estruturas tectónicas, eventos históricos ou intervalos regionais que não apareçam literalmente na evidência fornecida.
- Se fault_context_loaded=false, não afirmes correlação ou ausência de correlação com nenhuma falha ou estrutura específica.
- Se gnss_context_loaded=false ou insar_context_loaded=false, esses dados podem ser sugeridos apenas como trabalho futuro genérico; nunca como evidência observada.
- Se model_arena_available=false, não atribuas desempenho, leakage, overfitting ou skill a modelos que não foram executados.
- Quando a evidência não suporta uma afirmação, escreve explicitamente «não avaliável com a evidência fornecida».

LIMITES CIENTÍFICOS:
- Distingue anomalia estatística de interpretação tectónica.
- Não declares sismos iminentes e não transformes score, b-value, migração ou consenso em previsão.
- Identifica limitações e discordâncias.

FORMATO DE BAIXO CONSUMO:
Responde em português europeu, em no máximo ~300 palavras. Usa frases curtas e bullets. Produz exatamente estes 4 blocos: VEREDITO, EVIDÊNCIA, FRAGILIDADES, RECOMENDAÇÃO. Prioriza 2-4 pontos por bloco e não repitas números desnecessariamente. Não termines uma frase a meio."""


def _chair_system(evidence_date: str | None) -> str:
    date_rule = (
        f"A data da evidência é {evidence_date}. Se mostrares uma data, usa exatamente este valor; nunca uses placeholders."
        if evidence_date
        else "Não inventes uma data se ela não estiver disponível na evidência."
    )
    return f"""És o Chair do MEMÓRIA Scientific Council. Consolida revisões independentes sem apagar discordâncias.
{date_rule}

POLÍTICA DE GROUNDING OBRIGATÓRIA:
- Usa apenas a evidência fornecida e as revisões grounded incluídas no contexto.
- Não introduzas novas instituições, catálogos, falhas, estruturas tectónicas, eventos históricos, valores regionais ou factos externos.
- Se a evidência não contém contexto geológico independente, mantém a interpretação tectónica como não confirmada/não avaliável.
- Não transformes recomendações dos revisores em evidência observada.
- Nunca uses «[Data atual]», «[data atual]» ou outro placeholder.

LIMITES:
- Nunca faz previsão sísmica, não declara sismos iminentes e não assume validação institucional.
- Preserva explicitamente desacordos relevantes entre agentes.

FORMATO DE BAIXO CONSUMO:
Produz em no máximo ~380 palavras, com frases curtas e sem repetir todas as métricas dos revisores. Usa exatamente estes 5 blocos: CONSENSO, DISCORDÂNCIAS, FORÇA DA EVIDÊNCIA, DECISÃO DE USO, PRÓXIMOS TESTES. Não termines uma frase a meio."""


def _has_required_headings(text: str, headings: tuple[str, ...]) -> bool:
    upper = text.upper()
    return all(heading in upper for heading in headings)


def _sensor_claims_without_context(text: str, sensor: str) -> list[str]:
    """Detect only affirmative uses of an unavailable sensor as observed evidence.

    Mentions that explicitly describe absence, non-evaluability or future work are
    allowed. This avoids the v2.0.3 false positive where phrases such as
    "seria útil obter GNSS" were treated as if GNSS had been observed.
    """
    units = [unit.strip() for unit in re.split(r"(?<=[.!?])\s+|\n+", text) if unit.strip()]
    sensor_folded = sensor.casefold()
    safe_markers = (
        "não disponível", "indisponível", "não carreg", "sem dados",
        "ausência de", "não existe", "não existem", "não foi fornecid",
        "não foram fornecid", "não avaliável", "não pode ser avaliad",
        "não é possível", "seria útil", "seria necessário", "recomenda",
        "obter ", "adicionar ", "integrar ", "trabalho futuro",
        "se disponível", "quando disponível", "evidência independente",
        "carece de", "falta de", "limitação",
    )
    evidence_markers = (
        "mostra", "confirma", "indica", "deteta", "detecta", "revela",
        "mede", "mediu", "regista", "registou", "observa", "observou",
        "corrobora", "suporta", "sinaliza", "demonstra", "evidencia",
        "apresenta", "deslocamento", "deformação", "deformacao", "strain",
        "velocidade",
    )
    issues: list[str] = []
    for unit in units:
        folded = unit.casefold()
        if sensor_folded not in folded:
            continue
        if any(marker in folded for marker in safe_markers):
            continue
        numeric_claim = bool(re.search(rf"\b{re.escape(sensor)}\b[^\n]{{0,80}}[-+]?\d+(?:[.,]\d+)?", unit, re.IGNORECASE))
        affirmative_claim = any(marker in folded for marker in evidence_markers)
        if numeric_claim or affirmative_claim:
            issues.append(unit[:220])
    return issues


def _validate_grounding(text: str, evidence_context: str) -> tuple[str, ...]:
    issues: list[str] = []
    evidence_folded = evidence_context.casefold()
    manifest = _grounding_manifest(evidence_context)

    if re.search(r"\[\s*data\s+atual\s*\]", text, flags=re.IGNORECASE):
        issues.append("placeholder de data")

    for entity in HIGH_RISK_NAMED_ENTITIES:
        if entity.casefold() in text.casefold() and entity.casefold() not in evidence_folded:
            issues.append(f"entidade externa não suportada: {entity}")

    fault_loaded = bool(manifest.get("fault_context_loaded", False))
    if not fault_loaded:
        named_fault_pattern = re.compile(
            r"\b(?:falha|fault|banco|fossa|dorsal|zona\s+de\s+fratura|zona\s+de\s+fractura)\s+(?:de\s+|do\s+|da\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ-]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ-]+){0,4}",
            flags=re.UNICODE,
        )
        for match in named_fault_pattern.findall(text):
            if match.casefold() not in evidence_folded:
                issues.append(f"estrutura tectónica nomeada sem contexto carregado: {match}")

    if not bool(manifest.get("gnss_context_loaded", False)):
        if _sensor_claims_without_context(text, "GNSS"):
            issues.append("GNSS usado afirmativamente como evidência sem contexto GNSS carregado")
    if not bool(manifest.get("insar_context_loaded", False)):
        if _sensor_claims_without_context(text, "InSAR"):
            issues.append("InSAR usado afirmativamente como evidência sem contexto InSAR carregado")

    return tuple(dict.fromkeys(issues))


def _replace_date_placeholders(text: str, evidence_date: str | None) -> str:
    if not evidence_date:
        return text
    result = re.sub(r"\[\s*data\s+atual\s*\]", evidence_date, text, flags=re.IGNORECASE)
    result = re.sub(r"\bData\s+atual\b", evidence_date, result, flags=re.IGNORECASE)
    return result


def _safe_issue_summary(issues: tuple[str, ...]) -> str:
    cleaned: list[str] = []
    for issue in issues:
        if issue.startswith("entidade externa não suportada:"):
            cleaned.append("entidade externa não suportada")
        elif issue.startswith("estrutura tectónica nomeada sem contexto carregado:"):
            cleaned.append("estrutura tectónica nomeada sem contexto carregado")
        else:
            cleaned.append(issue)
    return "; ".join(dict.fromkeys(cleaned)) if cleaned else "resposta incompleta"


def _response_usage(response: MistralAssistantResponse) -> tuple[int, int, int]:
    prompt = int(response.prompt_tokens or 0)
    completion = int(response.completion_tokens or 0)
    total = int(response.total_tokens or 0)
    if not total and (prompt or completion):
        total = prompt + completion
    return prompt, completion, total


def _safe_fallback(
    role: str,
    issues: tuple[str, ...],
    model: str,
    attempts: int,
    *,
    api_requests: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> CouncilReview:
    issue_text = _safe_issue_summary(issues)
    text = (
        "VEREDITO\nRevisão automática não publicada porque não passou integralmente o controlo de grounding/completude.\n\n"
        "EVIDÊNCIA\nOs cálculos científicos do MEMÓRIA permanecem disponíveis no dashboard e não foram alterados pelo agente.\n\n"
        f"FRAGILIDADES\nO output do agente apresentou: {issue_text}.\n\n"
        "RECOMENDAÇÃO\nReexecutar o agente. Até existir uma resposta grounded completa, não usar esta revisão como evidência científica."
    )
    return CouncilReview(
        agent=role,
        text=text,
        model=model,
        grounding_passed=False,
        grounding_issues=issues,
        attempts=attempts,
        api_requests=api_requests,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _run_agent(
    client: MistralAssistantClient,
    role: str,
    mission: str,
    evidence_context: str,
) -> CouncilReview:
    system_prompt = _agent_system(role, mission)
    role_context = _compact_evidence_for_role(evidence_context, role)
    question = "Avalia criticamente o MEMÓRIA apenas na tua especialidade e apenas com a evidência fornecida."
    last_response: MistralAssistantResponse | None = None
    last_issues: tuple[str, ...] = tuple()
    api_requests = prompt_tokens = completion_tokens = total_tokens = 0

    for attempt in (1, 2):
        if attempt == 2:
            problem = "; ".join(last_issues) if last_issues else "faltam blocos obrigatórios ou a resposta ficou incompleta"
            question = (
                "Reescreve integralmente e de forma mais curta. Corrige: "
                f"{problem}. Mantém os quatro blocos, usa apenas a evidência e termina todas as frases."
            )
        token_budget = AGENT_TOKEN_BUDGETS[role] + (RETRY_TOKEN_BONUS if attempt == 2 else 0)
        response = client.complete_with_system(
            system_prompt=system_prompt,
            question=question,
            context_text=role_context,
            max_tokens=token_budget,
        )
        last_response = response
        api_requests += 1
        p, c, t = _response_usage(response)
        prompt_tokens += p
        completion_tokens += c
        total_tokens += t

        grounding_issues = _validate_grounding(response.text, role_context)
        completeness_issues: list[str] = []
        if not _has_required_headings(response.text, AGENT_HEADINGS):
            completeness_issues.append("blocos obrigatórios em falta")
        if getattr(response, "finish_reason", None) == "length":
            completeness_issues.append("resposta truncada pelo limite de tokens")
        last_issues = tuple(dict.fromkeys([*grounding_issues, *completeness_issues]))
        if not last_issues:
            return CouncilReview(
                agent=role,
                text=response.text,
                model=response.model,
                grounding_passed=True,
                grounding_issues=tuple(),
                attempts=attempt,
                finish_reason=getattr(response, "finish_reason", None),
                api_requests=api_requests,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

    assert last_response is not None
    return _safe_fallback(
        role,
        last_issues,
        last_response.model,
        2,
        api_requests=api_requests,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _local_no_grounded_chair(evidence_context: str, reviews: list[CouncilReview]) -> CouncilReview:
    date = _evidence_date(evidence_context)
    rejected = ", ".join(review.agent for review in reviews) or "nenhum revisor"
    date_text = f" Data da evidência: {date}." if date else ""
    text = (
        "CONSENSO\nNão foi executada síntese LLM porque nenhum revisor passou o controlo de grounding/completude."
        f"{date_text}\n\n"
        "DISCORDÂNCIAS\nNão existem revisões grounded suficientes para consolidar discordâncias científicas. "
        f"Revisores rejeitados: {rejected}.\n\n"
        "FORÇA DA EVIDÊNCIA\nNão reclassificada pelo Chair. Os cálculos determinísticos do MEMÓRIA permanecem disponíveis e inalterados.\n\n"
        "DECISÃO DE USO\nResearch-only. A camada de revisão por agentes não deve ser usada nesta execução.\n\n"
        "PRÓXIMOS TESTES\nCorrigir/reexecutar apenas os revisores rejeitados. O Chair será chamado quando existir pelo menos uma revisão grounded."
    )
    return CouncilReview(
        agent="Chair",
        text=text,
        model="local-deterministic",
        grounding_passed=False,
        grounding_issues=("nenhum revisor grounded; Chair LLM não executado",),
        attempts=0,
        api_requests=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )


def _run_chair(
    client: MistralAssistantClient,
    evidence_context: str,
    reviews: list[CouncilReview],
) -> CouncilReview:
    evidence_date = _evidence_date(evidence_context)
    grounded_reviews = [review for review in reviews if review.grounding_passed]
    if not grounded_reviews:
        return _local_no_grounded_chair(evidence_context, reviews)
    digest = "\n\n".join(f"### {review.agent}\n{review.text}" for review in grounded_reviews)
    chair_context = _compact_chair_evidence(evidence_context) + "\n\nREVISORES GROUNDED:\n" + digest
    question = "Produz a síntese final usando apenas o resumo de evidência e as revisões grounded."
    last_response: MistralAssistantResponse | None = None
    last_issues: tuple[str, ...] = tuple()
    api_requests = prompt_tokens = completion_tokens = total_tokens = 0

    for attempt in (1, 2):
        if attempt == 2:
            problem = "; ".join(last_issues) if last_issues else "síntese incompleta"
            question = (
                "Reescreve integralmente e mais curto. Corrige: "
                f"{problem}. Mantém os cinco blocos, sem placeholders nem evidência externa."
            )
        token_budget = CHAIR_TOKEN_BUDGET + (RETRY_TOKEN_BONUS if attempt == 2 else 0)
        response = client.complete_with_system(
            system_prompt=_chair_system(evidence_date),
            question=question,
            context_text=chair_context,
            max_tokens=token_budget,
        )
        last_response = response
        api_requests += 1
        p, c, t = _response_usage(response)
        prompt_tokens += p
        completion_tokens += c
        total_tokens += t

        text = _replace_date_placeholders(response.text, evidence_date)
        grounding_issues = _validate_grounding(text, evidence_context)
        completeness_issues: list[str] = []
        if not _has_required_headings(text, CHAIR_HEADINGS):
            completeness_issues.append("blocos obrigatórios do Chair em falta")
        if getattr(response, "finish_reason", None) == "length":
            completeness_issues.append("síntese truncada pelo limite de tokens")
        last_issues = tuple(dict.fromkeys([*grounding_issues, *completeness_issues]))
        if not last_issues:
            return CouncilReview(
                agent="Chair",
                text=text,
                model=response.model,
                grounding_passed=True,
                grounding_issues=tuple(),
                attempts=attempt,
                finish_reason=getattr(response, "finish_reason", None),
                api_requests=api_requests,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

    assert last_response is not None
    issue_text = _safe_issue_summary(last_issues)
    fallback_text = (
        "CONSENSO\nNão foi publicada uma síntese automática porque o output do Chair não passou integralmente o controlo de grounding/completude.\n\n"
        "DISCORDÂNCIAS\nConsultar diretamente as revisões individuais grounded apresentadas acima.\n\n"
        "FORÇA DA EVIDÊNCIA\nNão reclassificada pelo Chair. Os resultados numéricos do MEMÓRIA permanecem inalterados.\n\n"
        "DECISÃO DE USO\nResearch-only.\n\n"
        f"PRÓXIMOS TESTES\nReexecutar o Chair; problema detetado: {issue_text}."
    )
    return CouncilReview(
        agent="Chair",
        text=fallback_text,
        model=last_response.model,
        grounding_passed=False,
        grounding_issues=last_issues,
        attempts=2,
        finish_reason=getattr(last_response, "finish_reason", None),
        api_requests=api_requests,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def run_scientific_council(
    client: MistralAssistantClient,
    evidence_context: str,
    agents: Iterable[str] | None = None,
) -> CouncilResult:
    selected = list(agents or AGENT_ROLES.keys())
    unknown = [role for role in selected if role not in AGENT_ROLES]
    if unknown:
        raise ValueError(f"Agentes desconhecidos: {', '.join(unknown)}")

    # Sequential execution is intentional: it avoids request bursts on low-rate API tiers.
    reviews = [_run_agent(client, role, AGENT_ROLES[role], evidence_context) for role in selected]
    synthesis = _run_chair(client, evidence_context, reviews)
    return CouncilResult(tuple(reviews), synthesis, evidence_date_utc=_evidence_date(evidence_context))
