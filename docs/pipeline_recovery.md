# Recuperar a pipeline após uma falha Silver

## O que aconteceu

A escrita Parquet falhou porque `source_event_id` continha identificadores
numéricos e textuais. Como existia um Parquet anterior de demonstração, o
`build-gold` leu esse ficheiro antigo. Por isso foram novamente produzidos
6 648 fingerprints de demonstração.

O relatório falhou separadamente porque `pandas.DataFrame.to_markdown`
necessitava do pacote opcional `tabulate`.

## Correções na versão 0.1.3

- Todas as colunas textuais são convertidas para `pandas.StringDtype`.
- CSV e Parquet são escritos de forma atómica.
- Se Parquet falhar, qualquer Parquet antigo é removido.
- O carregador não prefere Parquet quando o CSV é mais recente.
- `build-gold` recusa dados exclusivamente DEMO quando existem fontes Bronze reais.
- O relatório tem um renderizador Markdown interno.
- `tabulate` passou também a fazer parte das dependências.
- CSVs normalizados de conveniência deixam de ser ingeridos novamente.
- Foram adicionados `clean-derived` e `data-status`.

## Sequência recomendada

```cmd
.venv\Scripts\activate
python -m pip install --upgrade -e .
python -m src.pipeline clean-derived
python -m src.pipeline build-silver
python -m src.pipeline build-gold
python -m src.pipeline report
python -m src.pipeline data-status
python -m streamlit run app\streamlit_app.py
```

Para recolher novamente o IPMA antes da reconstrução:

```cmd
python -m src.pipeline run-all --ipma-areas 7 3
```
