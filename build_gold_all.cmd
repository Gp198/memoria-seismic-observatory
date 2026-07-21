@echo off
setlocal
call .venv\Scripts\activate
python -m src.pipeline build-gold --catalogue-mode complete --magnitude-policy operational || exit /b 1
python -m src.pipeline build-gold --catalogue-mode declustered --magnitude-policy operational || exit /b 1
python -m src.pipeline build-gold --catalogue-mode complete --magnitude-policy validated || exit /b 1
python -m src.pipeline build-gold --catalogue-mode declustered --magnitude-policy validated || exit /b 1
python -m src.pipeline merge-gold || exit /b 1
echo Gold complete: 2 catalogue modes x 2 magnitude policies.
