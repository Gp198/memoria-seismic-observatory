from __future__ import annotations

import re
import unicodedata

PROJECT_IDENTITY_ANSWER = (
    "O MEMÓRIA foi criado e é desenvolvido por Gonçalo Pedro. É um projeto "
    "experimental independente e não é um projeto, produto, iniciativa ou "
    "serviço oficial do IPMA, nem foi criado por uma equipa do IPMA. O IPMA é "
    "uma das fontes públicas de dados integradas e a referência oficial para "
    "informação sísmica e segurança pública em Portugal."
)


def _normalise(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.lower()).strip()


def answer_identity_question(question: str) -> str | None:
    """Return a deterministic answer for authorship or IPMA-affiliation questions."""
    text = _normalise(question)
    if not text:
        return None
    mentions_project = any(
        token in text
        for token in (
            "memoria",
            "projeto",
            "project",
            "observatorio",
            "plataforma",
            "aplicacao",
        )
    )
    identity_intent = any(
        phrase in text
        for phrase in (
            "quem criou",
            "quem desenvolveu",
            "quem fez",
            "qual e o autor",
            "qual a autoria",
            "quem e o criador",
            "criado por quem",
            "desenvolvido por quem",
            "e do ipma",
            "projeto do ipma",
            "equipa do ipma",
            "relacao com o ipma",
            "relacao do memoria com o ipma",
            "qual e a relacao",
            "ligacao ao ipma",
            "afiliado ao ipma",
            "who created",
            "who developed",
            "created by",
            "is this an ipma project",
            "affiliated with ipma",
        )
    )
    if mentions_project and identity_intent:
        return PROJECT_IDENTITY_ANSWER
    return None


_FALSE_ATTRIBUTION_PATTERNS = (
    re.compile(
        r"\b(?:projeto|produto|plataforma|observatorio|iniciativa|servico)"
        r"(?:\s+experimental)?\s+(?:do|da|de)\s+(?:o\s+)?ipma\b"
    ),
    re.compile(
        r"\b(?:criado|desenvolvido|mantido|operado|produzido|financiado)"
        r"\s+(?:pela|pelo)\s+(?:equipa\s+do\s+)?ipma\b"
    ),
    re.compile(r"\bequipa\s+do\s+ipma\s+(?:criou|desenvolveu|mantem|opera)\b"),
)


def contains_false_ipma_attribution(text: str) -> bool:
    """Detect affirmative false attribution while allowing explicit negations."""
    normalised = _normalise(text)
    sentences = re.split(r"(?<=[.!?;])\s+|\n+", normalised)
    for sentence in sentences:
        if not sentence:
            continue
        for pattern in _FALSE_ATTRIBUTION_PATTERNS:
            match = pattern.search(sentence)
            if not match:
                continue
            prefix = sentence[max(0, match.start() - 55): match.start()]
            if any(negation in prefix for negation in ("nao ", "nunca ", "not ")):
                continue
            return True
    return False


def enforce_identity_guard(text: str) -> str:
    """Replace a response that falsely attributes MEMÓRIA to IPMA."""
    if contains_false_ipma_attribution(text):
        return (
            PROJECT_IDENTITY_ANSWER
            + " Esta correção prevalece sobre qualquer formulação anterior da conversa."
        )
    return text
