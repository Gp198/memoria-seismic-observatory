from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import streamlit as st

from src.assistant.context import context_to_text
from src.assistant.knowledge import QUICK_QUESTIONS
from src.assistant.mistral_client import (
    MistralAssistantClient,
    MistralAssistantConfig,
    MistralAssistantError,
)

_MESSAGES_KEY = "memoria_assistant_messages"
_SESSION_KEY = "memoria_mistral_api_key_session"
_LAST_ERROR_KEY = "memoria_assistant_last_error"
_HISTORY_VERSION_KEY = "memoria_assistant_history_version"
_HISTORY_SCHEMA_VERSION = "0.6.1"


def _secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError, AttributeError):
        value = None
    if value:
        return str(value).strip()
    value = os.getenv(name)
    return str(value).strip() if value else None


def _api_key() -> tuple[str | None, str]:
    secret_value = _secret("MISTRAL_API_KEY")
    if secret_value:
        return secret_value, "ambiente/segredo"
    session_value = st.session_state.get(_SESSION_KEY)
    if session_value:
        return str(session_value), "sessão"
    return None, "não configurada"


def _setting(name: str, default: str) -> str:
    return _secret(name) or default




def _float_setting(name: str, default: float) -> float:
    try:
        return float(_setting(name, str(default)))
    except (TypeError, ValueError):
        return default


def _int_setting(name: str, default: int) -> int:
    try:
        return int(_setting(name, str(default)))
    except (TypeError, ValueError):
        return default


def _messages() -> list[dict[str, Any]]:
    if st.session_state.get(_HISTORY_VERSION_KEY) != _HISTORY_SCHEMA_VERSION:
        st.session_state[_MESSAGES_KEY] = []
        st.session_state[_HISTORY_VERSION_KEY] = _HISTORY_SCHEMA_VERSION
        st.session_state.pop(_LAST_ERROR_KEY, None)
    if _MESSAGES_KEY not in st.session_state:
        st.session_state[_MESSAGES_KEY] = []
    return st.session_state[_MESSAGES_KEY]


def _render_history(messages: list[dict[str, Any]]) -> None:
    if not messages:
        st.caption(
            "Pergunta-me o significado dos indicadores, diferenças entre modos, "
            "limitações ou funcionalidades desta página."
        )
        return
    for message in messages[-6:]:
        role = message.get("role")
        label = "Tu" if role == "user" else "Assistente"
        icon = "◉" if role == "assistant" else "›"
        st.markdown(f"**{icon} {label}**")
        st.markdown(str(message.get("content", "")))


def _save_session_key() -> None:
    value = st.session_state.get("memoria_mistral_key_input", "").strip()
    if value:
        st.session_state[_SESSION_KEY] = value
        st.session_state.pop(_LAST_ERROR_KEY, None)


def render_assistant_panel(
    *,
    context: Mapping[str, Any],
    expanded: bool = False,
) -> None:
    enabled = _setting("MEMORIA_ASSISTANT_ENABLED", "true").lower() not in {
        "0", "false", "no", "off"
    }
    if not enabled:
        st.caption("Assistente IA desativado por configuração.")
        return

    with st.expander("✦ Assistente MEMÓRIA", expanded=expanded):
        st.caption(
            "Explicações contextuais com Mistral. Apenas métricas agregadas e a "
            "pergunta são enviadas; o catálogo bruto e a chave não são enviados."
        )
        st.info(
            "O MEMÓRIA é um projeto experimental independente criado e "
            "desenvolvido por Gonçalo Pedro. Não é um produto oficial do IPMA."
        )
        api_key, key_source = _api_key()
        if not api_key:
            st.warning("API Mistral não configurada.")
            st.text_input(
                "MISTRAL_API_KEY",
                type="password",
                key="memoria_mistral_key_input",
                help="A chave fica apenas na sessão do Streamlit e não é gravada em ficheiro.",
            )
            st.button(
                "Usar chave nesta sessão",
                on_click=_save_session_key,
                width="stretch",
            )
            st.caption(
                "Para configuração permanente, usa a variável MISTRAL_API_KEY "
                "ou .streamlit/secrets.toml."
            )
            return

        model = _setting("MEMORIA_MISTRAL_MODEL", "mistral-small-latest")
        st.success(f"Configurado · {model} · chave por {key_source}")

        messages = _messages()
        _render_history(messages)
        if st.session_state.get(_LAST_ERROR_KEY):
            st.error(st.session_state[_LAST_ERROR_KEY])

        suggestion = st.selectbox(
            "Pergunta rápida",
            ["Escrever a minha pergunta..."] + QUICK_QUESTIONS,
            key="memoria_assistant_suggestion",
        )
        with st.form("memoria_assistant_form", clear_on_submit=True):
            typed_question = st.text_area(
                "Pergunta",
                placeholder="Ex.: Porque é que o intervalo de incerteza é tão largo?",
                height=92,
                max_chars=2500,
            )
            submitted = st.form_submit_button(
                "Perguntar ao assistente",
                type="primary",
                width="stretch",
            )

        clear_col, key_col = st.columns(2)
        if clear_col.button("Limpar conversa", width="stretch"):
            st.session_state[_MESSAGES_KEY] = []
            st.session_state.pop(_LAST_ERROR_KEY, None)
            st.rerun()
        if key_source == "sessão" and key_col.button(
            "Remover chave", width="stretch"
        ):
            st.session_state.pop(_SESSION_KEY, None)
            st.session_state.pop(_LAST_ERROR_KEY, None)
            st.rerun()

        if not submitted:
            return
        question = typed_question.strip()
        if not question and suggestion != "Escrever a minha pergunta...":
            question = suggestion
        if not question:
            st.session_state[_LAST_ERROR_KEY] = "Escreve ou seleciona uma pergunta."
            st.rerun()

        config = MistralAssistantConfig(
            api_key=api_key,
            model=model,
            base_url=_setting("MEMORIA_MISTRAL_BASE_URL", "https://api.mistral.ai/v1"),
            timeout_seconds=_float_setting("MEMORIA_MISTRAL_TIMEOUT", 45.0),
            max_tokens=_int_setting("MEMORIA_MISTRAL_MAX_TOKENS", 700),
            temperature=_float_setting("MEMORIA_MISTRAL_TEMPERATURE", 0.15),
            max_retries=_int_setting("MEMORIA_MISTRAL_MAX_RETRIES", 2),
            max_history_messages=_int_setting("MEMORIA_ASSISTANT_MAX_HISTORY", 8),
        )
        client = MistralAssistantClient(config)
        try:
            with st.spinner("A interpretar o contexto atual..."):
                response = client.complete(
                    question=question,
                    context_text=context_to_text(context),
                    history=messages,
                )
        except (MistralAssistantError, ValueError) as error:
            st.session_state[_LAST_ERROR_KEY] = str(error)
            st.rerun()

        messages.append({"role": "user", "content": question})
        messages.append(
            {
                "role": "assistant",
                "content": response.text,
                "model": response.model,
                "total_tokens": response.total_tokens,
            }
        )
        st.session_state[_MESSAGES_KEY] = messages[-12:]
        st.session_state.pop(_LAST_ERROR_KEY, None)
        st.rerun()
