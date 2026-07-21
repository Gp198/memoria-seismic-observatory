# MEMÓRIA v0.6.0 — Assistente explicativo Mistral

## Objetivo

O Assistente MEMÓRIA explica métricas, resultados, limitações e funcionalidades
sem alterar os pipelines, os cálculos científicos ou os dados Silver/Gold.
É carregado de forma independente e só chama a API quando o utilizador submete
uma pergunta.

## Arquitetura

```text
Streamlit dashboard
  └─ contexto agregado da página
       ├─ seleção atual
       ├─ métricas do fingerprint
       ├─ resultados de similaridade/replay
       └─ limites científicos
            ↓
       Mistral Chat Completions
            ↓
       resposta explicativa em português
```

Não são enviados:

- linhas brutas do catálogo;
- coordenadas individuais;
- ficheiros Bronze, Silver ou Gold;
- a chave da API dentro do prompt;
- dados pessoais.

## Configuração

### Variável de ambiente no Windows CMD

```cmd
set MISTRAL_API_KEY=a_tua_chave
set MEMORIA_MISTRAL_MODEL=mistral-small-latest
python -m streamlit run app\streamlit_app.py
```

### Streamlit secrets

Cria `.streamlit/secrets.toml`:

```toml
MISTRAL_API_KEY = "a_tua_chave"
MEMORIA_MISTRAL_MODEL = "mistral-small-latest"
```

O ficheiro real já está protegido pelo `.gitignore`.

### Chave temporária

Quando não existe uma variável ou secret, a interface permite inserir uma chave
apenas para a sessão atual. A chave não é escrita no projeto.

## Segurança científica

O system prompt impede o assistente de:

- prever deterministicamente data, local ou magnitude;
- declarar iminência ou segurança absoluta;
- transformar percentis ou semelhança em causalidade;
- substituir informação oficial do IPMA ou da Proteção Civil;
- ocultar baixa cobertura validada ou amostras insuficientes.

## Resiliência

- timeout configurável;
- repetição limitada para HTTP 429 e erros 5xx;
- mensagens próprias para 401, 402, 429 e falhas TLS;
- histórico limitado para reduzir consumo da quota gratuita;
- resposta máxima configurável;
- nenhum pedido é feito durante ingestão, Silver, Gold ou Replay.

## Limitações

O chatbot explica o contexto disponível no dashboard. Não pesquisa a Internet,
não obtém sismicidade em tempo real e não deve ser usado como fonte oficial.
A qualidade da resposta depende do modelo Mistral e da qualidade das métricas
fornecidas pela aplicação.
