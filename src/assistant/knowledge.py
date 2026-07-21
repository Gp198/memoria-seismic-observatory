from __future__ import annotations

APP_KNOWLEDGE = {
    "identity": {
        "creator": "Gonçalo Pedro",
        "status": "Projeto experimental independente",
        "ipma_relationship": (
            "O MEMÓRIA não é um projeto, produto, iniciativa ou serviço oficial "
            "do IPMA e não foi criado por uma equipa do IPMA. O IPMA é uma fonte "
            "pública de dados integrada e a referência oficial para informação "
            "sísmica e segurança pública em Portugal."
        ),
        "non_affiliation": (
            "Não existe afiliação, patrocínio, validação ou endosso institucional "
            "do IPMA implícito no uso dos seus dados públicos."
        ),
    },
    "purpose": (
        "O MEMÓRIA é um observatório experimental de inteligência sísmica "
        "explicável. Compara estados relativos, mede incerteza e executa replay "
        "retrospetivo. Não é um sistema de previsão determinística ou alerta."
    ),
    "pages": {
        "Visão geral": (
            "Resume o estado relativo da região selecionada, o percentil dentro "
            "de uma época comparável, a incerteza, a qualidade e a distribuição "
            "espacial e temporal do catálogo."
        ),
        "Memória semelhante": (
            "Procura famílias temporais historicamente semelhantes ao estado "
            "selecionado. A semelhança é matemática e não demonstra causalidade "
            "nem capacidade de previsão."
        ),
        "Replay Portugal": (
            "Simula o que o sistema teria produzido numa data histórica usando "
            "apenas informação conhecida até essa data. Compara famílias análogas, "
            "frequência empírica e Poisson."
        ),
        "Qualidade e metodologia": (
            "Audita fontes, deduplicação, declustering, completude, proveniência "
            "das magnitudes e limitações científicas."
        ),
    },
    "concepts": {
        "percentile": (
            "O percentil posiciona a taxa atual face a janelas anteriores da "
            "mesma época e domínio, acima de um limiar comparável. Não é uma "
            "probabilidade de um grande sismo."
        ),
        "confidence_interval": (
            "O intervalo de incerteza mostra a precisão limitada da posição "
            "percentílica. Intervalos largos impedem classificações fortes."
        ),
        "declustering": (
            "O modo declusterizado piloto reduz o peso de réplicas e sequências. "
            "É uma análise de sensibilidade e não um catálogo oficial."
        ),
        "magnitude_policy": (
            "A política operacional auditada inclui fallbacks sinalizados. A "
            "política validada usa apenas Mw e regras revistas, podendo ter uma "
            "amostra muito pequena."
        ),
        "similarity": (
            "A semelhança mede proximidade entre fingerprints. Deve ser lida em "
            "conjunto com compatibilidade, dimensão da amostra e força da evidência."
        ),
        "replay": (
            "O replay é validação retrospetiva sem fuga temporal. O score das "
            "famílias não é uma probabilidade calibrada até demonstrar calibração "
            "walk-forward suficiente."
        ),
        "brier": (
            "O Brier Score mede o erro quadrático de estimativas probabilísticas; "
            "menor é melhor. O Brier Skill Score compara o método com uma linha "
            "de base."
        ),
        "completeness": (
            "A magnitude de completude estima acima de que magnitude o catálogo "
            "é mais consistente. Muda entre épocas, redes e regiões."
        ),
    },
    "boundaries": [
        "Não prever data, local ou magnitude de um sismo futuro.",
        "Não declarar iminência, segurança absoluta ou risco operacional.",
        "Não transformar semelhança ou percentil em causalidade.",
        "Indicar IPMA e Proteção Civil como fontes oficiais para segurança pública.",
        "Distinguir sempre catálogo completo/declusterizado e política operacional/validada.",
        "Quando a cobertura validada é baixa, declarar evidência insuficiente.",
    ],
}

QUICK_QUESTIONS = [
    "Explica os principais resultados desta página em linguagem simples.",
    "O que significa o percentil e o respetivo intervalo de incerteza?",
    "Qual é a diferença entre catálogo completo e declusterizado?",
    "Como devo interpretar a política de magnitude operacional e a validada?",
    "O que o Replay Portugal consegue demonstrar e o que não consegue?",
    "Quais são as principais limitações científicas da seleção atual?",
]
