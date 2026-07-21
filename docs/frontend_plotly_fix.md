# Correção do mapa Streamlit / Plotly

## Erro observado

```text
numpy.exceptions.DTypePromotionError:
DateTime64DType could not be promoted by Float64DType
```

O erro ocorria no `plotly.express.scatter_map`. O dataframe combinava:

- datas `datetime64[ns, UTC]`;
- números pandas nullable `Float64`;
- campos textuais `StringDtype`.

A camada Narwhals usada pelo Plotly tentou combinar esses valores numa única
matriz NumPy e falhou na promoção dos tipos.

## Correção 0.1.4

- Conversão dos números apresentados no dashboard para `float64` nativo.
- Datas do tooltip convertidas previamente para texto.
- Substituição de `px.scatter_map` por `go.Scattermap`.
- Tooltip pré-formatado numa única série textual.
- Testes específicos para `datetime64` com `Float64` nullable.

## Atualização

```cmd
.venv\Scripts\activate
python -m pip install --upgrade -e .
python -m streamlit run app\streamlit_app.py
```

Não é necessário voltar a executar as pipelines nem apagar os dados Silver e Gold.
