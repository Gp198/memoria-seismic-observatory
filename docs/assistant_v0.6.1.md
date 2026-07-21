# Assistente MEMÓRIA v0.6.1

## Identidade autoritativa

O assistente recebe factos de identidade de prioridade máxima: o MEMÓRIA foi criado e é desenvolvido por Gonçalo Pedro, é independente e não é um produto oficial do IPMA.

## Proteções adicionais

1. Perguntas sobre autoria ou relação com o IPMA são respondidas localmente, sem chamada à API.
2. O contexto enviado à Mistral inclui a identidade autoritativa do projeto.
3. O prompt proíbe inferências de afiliação a partir das fontes de dados.
4. Um guardião de saída substitui qualquer resposta que atribua afirmativamente o MEMÓRIA ao IPMA.
5. O histórico da v0.6.0 é limpo automaticamente para não perpetuar a resposta incorreta.
