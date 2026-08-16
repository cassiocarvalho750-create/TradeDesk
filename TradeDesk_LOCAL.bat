@echo off
REM ============================================================
REM  TradeDesk LOCAL - roda o scanner no seu PC e abre a pagina
REM ============================================================
cd /d C:\TradeDesk

echo.
echo === Rodando scanner US + B3 (diario) ===
echo Isso leva 1-2 minutos, aguarde...
echo.
python scanner_us.py
python scanner_b3.py

echo.
echo === Copiando os resultados para a pasta das paginas (docs) ===
REM o scanner gera os JSON na raiz; as paginas ficam em docs\.
REM copiamos os paineis recem-gerados para docs\ para a pagina ve-los.
copy /Y painel_us.json docs\ >nul 2>&1
copy /Y painel_b3.json docs\ >nul 2>&1
copy /Y painel_us_*.json docs\ >nul 2>&1
copy /Y painel_b3_*.json docs\ >nul 2>&1
copy /Y painel_etf*.json docs\ >nul 2>&1
copy /Y painel_forex*.json docs\ >nul 2>&1

echo.
echo === Abrindo a pagina no navegador ===
start "" http://localhost:8000/docs/TradeDesk.html
echo.
echo A pagina abriu no navegador. NAO feche esta janela preta
echo enquanto estiver usando (ela e o servidor).
echo Para encerrar, feche esta janela quando terminar.
echo.
python -m http.server 8000
