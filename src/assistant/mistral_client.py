from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from src.assistant.identity import answer_identity_question, enforce_identity_guard
from src.assistant.prompts import build_messages
from src.http_client import create_session


class MistralAssistantError(RuntimeError):
    """Base exception with a safe user-facing message."""


class MistralAuthenticationError(MistralAssistantError):
    pass


class MistralRateLimitError(MistralAssistantError):
    pass


@dataclass(frozen=True)
class MistralAssistantConfig:
    api_key: str
    model: str = "mistral-small-latest"
    base_url: str = "https://api.mistral.ai/v1"
    timeout_seconds: float = 45.0
    max_tokens: int = 700
    temperature: float = 0.15
    max_retries: int = 2
    max_history_messages: int = 8

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("A chave Mistral não foi configurada.")
        if self.timeout_seconds <= 0:
            raise ValueError("O timeout tem de ser positivo.")
        if self.max_tokens < 64:
            raise ValueError("max_tokens deve ser pelo menos 64.")


@dataclass(frozen=True)
class MistralAssistantResponse:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


def _extract_text(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise MistralAssistantError(
            "A API Mistral devolveu uma resposta sem conteúdo utilizável."
        ) from error

    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                candidate = item.get("text") or item.get("content")
                if isinstance(candidate, str):
                    chunks.append(candidate)
        text = "".join(chunks).strip()
    else:
        text = str(content).strip()

    if not text:
        raise MistralAssistantError(
            "A API Mistral devolveu uma resposta vazia."
        )
    return text


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class MistralAssistantClient:
    def __init__(
        self,
        config: MistralAssistantConfig,
        session: requests.Session | None = None,
        sleep_function=time.sleep,
    ) -> None:
        self.config = config
        self.session = session or create_session()
        self._sleep = sleep_function

    @property
    def endpoint(self) -> str:
        return self.config.base_url.rstrip("/") + "/chat/completions"

    def complete(
        self,
        *,
        question: str,
        context_text: str,
        history: list[dict[str, str]] | None = None,
    ) -> MistralAssistantResponse:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("A pergunta não pode estar vazia.")
        if len(cleaned_question) > 2500:
            raise ValueError("A pergunta excede o limite de 2 500 caracteres.")

        identity_answer = answer_identity_question(cleaned_question)
        if identity_answer:
            return MistralAssistantResponse(
                text=identity_answer,
                model="memoria-local-identity-v0.6.1",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            )

        payload = {
            "model": self.config.model,
            "messages": build_messages(
                question=cleaned_question,
                context_text=context_text,
                history=history or [],
                max_history_messages=self.config.max_history_messages,
            ),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "safe_prompt": True,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MEMORIA-Seismic-Observatory/0.6.1",
        }

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
            except requests.Timeout as error:
                last_error = error
                if attempt < self.config.max_retries:
                    self._sleep(min(2**attempt, 4))
                    continue
                raise MistralAssistantError(
                    "A API Mistral não respondeu dentro do tempo limite."
                ) from error
            except requests.RequestException as error:
                raise MistralAssistantError(
                    "Não foi possível contactar a API Mistral. Verifica a ligação e o certificado TLS."
                ) from error

            if response.status_code == 401:
                raise MistralAuthenticationError(
                    "A chave Mistral foi recusada. Confirma MISTRAL_API_KEY."
                )
            if response.status_code == 402:
                raise MistralAssistantError(
                    "A conta Mistral não permite este pedido. Confirma o plano, quota e modelo configurado."
                )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_seconds = min(float(retry_after), 8.0) if retry_after else min(2**attempt, 6)
                except (TypeError, ValueError):
                    wait_seconds = min(2**attempt, 6)
                if attempt < self.config.max_retries:
                    self._sleep(wait_seconds)
                    continue
                raise MistralRateLimitError(
                    "O limite da API Mistral foi atingido. Aguarda alguns instantes e tenta novamente."
                )
            if response.status_code >= 500:
                last_error = RuntimeError(f"Mistral HTTP {response.status_code}")
                if attempt < self.config.max_retries:
                    self._sleep(min(2**attempt, 4))
                    continue
                raise MistralAssistantError(
                    "A API Mistral está temporariamente indisponível."
                ) from last_error
            if response.status_code >= 400:
                detail = ""
                try:
                    detail = str(response.json().get("message") or response.json().get("detail") or "")
                except (ValueError, AttributeError):
                    detail = ""
                suffix = f" Detalhe: {detail[:240]}" if detail else ""
                raise MistralAssistantError(
                    f"O pedido ao assistente foi rejeitado (HTTP {response.status_code}).{suffix}"
                )

            try:
                data = response.json()
            except ValueError as error:
                raise MistralAssistantError(
                    "A API Mistral devolveu JSON inválido."
                ) from error
            usage = data.get("usage") or {}
            return MistralAssistantResponse(
                text=enforce_identity_guard(_extract_text(data)),
                model=str(data.get("model") or self.config.model),
                prompt_tokens=_optional_int(usage.get("prompt_tokens")),
                completion_tokens=_optional_int(usage.get("completion_tokens")),
                total_tokens=_optional_int(usage.get("total_tokens")),
            )

        raise MistralAssistantError(
            "Não foi possível concluir o pedido ao assistente."
        ) from last_error
