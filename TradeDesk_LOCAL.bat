@echo off
REM ============================================================
REM  TradeDesk LOCAL - roda o scanner no seu PC e abre a pagina
REM  Usa uma pasta separada (_local) que o Git NAO rastreia, entao
REM  nunca gera conflito com os arquivos da nuvem (docs/).
REM ============================================================
cd /d C:\TradeDesk

echo.
echo === Rodando scanner US + B3 (diario) ===
echo Isso leva 1-2 minutos, aguarde...
echo.
python scanner_us.py
python scanner_b3.py

echo.
echo === Preparando a pasta local de visualizacao (_local) ===
if not exist _local mkdir _local
REM copia as paginas (de docs) e os JSON recem-gerados (da raiz) para _local.
REM _local e ignorado pelo Git, entao nada disso vira conflito.
copy /Y docs\TradeDesk*.html _local\ >nul 2>&1
copy /Y painel_us*.json _local\ >nul 2>&1
copy /Y painel_b3*.json _local\ >nul 2>&1
copy /Y painel_etf*.json _local\ >nul 2>&1
copy /Y painel_forex*.json _local\ >nul 2>&1

echo.
echo === Abrindo a pagina no navegador ===
start "" http://localhost:8000/TradeDesk.html
echo.
echo A pagina abriu no navegador. NAO feche esta janela preta
echo enquanto estiver usando (ela e o servidor).
echo Para encerrar, feche esta janela quando terminar.
echo.
cd _local
python -m http.server 8000
