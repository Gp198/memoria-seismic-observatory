MEMÓRIA v2.0.4 — Scientific Robustness & Global Benchmarking

Patch sobre v2.0.3.

Principais alterações:
- Grounding Guard semântico: recomendações/ausência de GNSS e InSAR deixam de gerar falsos positivos; claims observacionais continuam bloqueados.
- Se 0 revisores passarem grounding, o Chair LLM não é chamado.
- b-value operacional passa a usar apenas a maior coorte coerente fonte + escala original na época atual; modo validado usa apenas magnitudes/conversões revistas.
- σ do b-value é identificado como estatístico e deixa de aparecer como ±0.00.
- UI distingue regime estatístico, anomalia estatística e interpretação tectónica.
- Model Arena ganha grelha magnitude × horizonte e leaderboard global por rank Brier, BSS, AP e vitórias.

Instalação:
1. Parar Streamlit.
2. Copiar o conteúdo do patch sobre a raiz do projeto v2.0.3.
3. Executar: python -m pip install --upgrade -e .
4. Testar: python -m pytest -q tests\test_v2_scientific_council.py tests\test_v2_seismology.py tests\test_v2_model_arena_leaderboard.py
5. Limpar cache: python -m streamlit cache clear
6. Iniciar: python -m streamlit run app\streamlit_app.py

Não é necessário reconstruir Bronze/Silver/Gold para aplicar o patch.
