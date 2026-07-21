# Migração para MEMÓRIA v0.6.0

A versão 0.6.0 adiciona o Assistente MEMÓRIA com Mistral. Não altera o esquema
Silver/Gold e não exige reconstrução dos dados derivados.

## Instalação

```cmd
cd C:\memoria-seismic-observatory
.venv\Scriptsctivate
python -m pip install --upgrade -e .
```

## Configurar a API

Opção recomendada para execução local:

```cmd
set MISTRAL_API_KEY=a_tua_chave
set MEMORIA_MISTRAL_MODEL=mistral-small-latest
python -m streamlit run app\streamlit_app.py
```

Para persistir a configuração local, copia:

```text
.streamlit\secrets.toml.example
```

para:

```text
.streamlit\secrets.toml
```

E substitui a chave de exemplo.

## Dados

Não é necessário executar `clean-derived`, `build-silver` ou `build-gold`.
A integração é exclusivamente de aplicação e não modifica resultados existentes.
