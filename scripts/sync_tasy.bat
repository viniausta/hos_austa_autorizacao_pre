@echo off
REM ============================================================
REM sync_tasy.bat — Sincroniza PDFs do Docker para o share do TASY
REM
REM O container Docker grava os PDFs em ./tasy-storage/anexo_opme/
REM Este script MOVE os arquivos para \\172.20.255.13\tasyausta\anexo_opme\
REM (move = copia + deleta origem, mantendo o destino para o TASY abrir)
REM
REM Agendar no Task Scheduler do Windows para rodar a cada 1 minuto.
REM ============================================================

set ORIGEM=%~dp0..\tasy-storage\anexo_opme
set DESTINO=\\172.20.255.13\tasyausta\anexo_opme

REM Garante que a pasta de origem existe
if not exist "%ORIGEM%" mkdir "%ORIGEM%"

REM Move todos os PDFs (copia para destino e deleta da origem)
robocopy "%ORIGEM%" "%DESTINO%" *.pdf /MOV /R:3 /W:5 /NP /LOG+:"%~dp0..\logs\sync_tasy.log" /TS
