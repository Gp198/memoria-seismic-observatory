# MEMÓRIA v0.1.6 — Executive frontend

## Correção

Foi removida a subtração direta entre timestamps históricos separados por
mais de 292 anos. A amplitude é calculada por anos civis, evitando
`OutOfBoundsDatetime` e `OverflowError`.

O Replay Portugal também utiliza `datetime` nativo de Python no cálculo da
taxa histórica para suportar catálogos milenares.

## Evolução visual

- navegação condicional: apenas a página selecionada é executada;
- cabeçalho executivo e barra lateral institucional;
- assinatura permanente `Criado por Gonçalo Pedro`;
- cartões de interpretação e estado;
- mapa com tooltips enriquecidos;
- agregação anual automática para séries históricas longas;
- apresentação profissional uniforme;
- rodapé institucional;
- substituição de `use_container_width` por `width="stretch"`.
