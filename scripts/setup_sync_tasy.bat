@echo off
REM ============================================================
REM setup_sync_tasy.bat — Cria tarefa agendada no Windows
REM que move PDFs para \\172.20.255.13\tasyausta\anexo_opme
REM
REM Executar UMA VEZ como Administrador.
REM Depois disso, roda sozinho para sempre (inclusive apos reboot).
REM ============================================================

set ORIGEM=%~dp0..\tasy-storage\anexo_opme
set DESTINO=\\172.20.255.13\tasyausta\anexo_opme
set LOGFILE=%~dp0..\logs\sync_tasy.log
set TASKNAME=RPA_SyncTasy_AnexoOPME

echo [setup] Criando tarefa agendada: %TASKNAME%
echo [setup] Origem:  %ORIGEM%
echo [setup] Destino: %DESTINO%
echo.

REM Cria a pasta de origem se nao existir
if not exist "%ORIGEM%" mkdir "%ORIGEM%"

REM Remove tarefa anterior (se existir)
schtasks /delete /tn "%TASKNAME%" /f >nul 2>&1

REM Cria tarefa que roda a cada 1 minuto, inicia com o sistema
schtasks /create ^
  /tn "%TASKNAME%" ^
  /tr "robocopy \"%ORIGEM%\" \"%DESTINO%\" *.pdf /MOV /R:2 /W:3 /NP /LOG+:\"%LOGFILE%\"" ^
  /sc minute /mo 1 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [setup] Tarefa criada com sucesso!
    echo [setup] Os PDFs serao movidos automaticamente a cada 1 minuto.
    echo [setup] Para verificar: schtasks /query /tn "%TASKNAME%"
    echo [setup] Para remover:   schtasks /delete /tn "%TASKNAME%" /f
    echo.
    echo [setup] Executando primeira sincronizacao agora...
    schtasks /run /tn "%TASKNAME%"
) else (
    echo [setup] ERRO ao criar tarefa. Execute como Administrador.
)

pause
