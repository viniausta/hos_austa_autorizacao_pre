@echo off
REM ============================================================
REM start.bat — Inicia Selenoid (Docker) + API Python (host)
REM
REM Executa tudo com um unico clique:
REM   1. Sobe Selenoid + Selenoid-UI no Docker
REM   2. Inicia a API FastAPI (Python) no Windows host
REM
REM O Python roda no host para ter acesso direto ao share de rede
REM do TASY (\\172.20.255.13\tasyausta\anexo_opme).
REM ============================================================

echo [start] Subindo Selenoid (Docker)...
docker compose up -d

echo [start] Aguardando Selenoid ficar pronto...
timeout /t 5 /nobreak >nul

echo [start] Iniciando API Python na porta 8000...
python api_server.py
