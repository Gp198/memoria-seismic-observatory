@echo off
setlocal
echo MEMORIA v2.0.0 - Explainable Seismic ^& Tectonic Intelligence

echo.
echo Copie todo o conteudo desta pasta para:
echo   C:\memoria-seismic-observatory
echo e aceite a substituicao dos ficheiros.
echo.
echo Depois execute:
echo   .venv\Scripts\activate
echo   python -m pip install --upgrade -e .
echo   python -m src.pipeline clean-derived
echo   python -m src.pipeline build-silver
echo   build_gold_all.cmd
echo   python -m src.pipeline tectonic-status --window 90
echo   python -m streamlit cache clear
echo   python -m streamlit run app\streamlit_app.py
echo.
echo Os dados Bronze nao sao alterados pelo patch.
echo GNSS, InSAR e faults sao opcionais; o MEMORIA nao cria evidencia geofisica ficticia.
pause
