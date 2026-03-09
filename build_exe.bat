@echo off
REM Script para gerar executável do RPA de Autorizações PA
REM Uso: run_build.bat

echo.
echo ========================================
echo  BUILD EXE - RPA Autorizacoes PA
echo ========================================
echo.

REM Verifica se PyInstaller está instalado
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller não encontrado. Instalando...
    pip install pyinstaller
)

echo [*] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
del *.spec 2>nul

echo [*] Gerando executável com PyInstaller...
pyinstaller build_exe.spec

echo.
if exist dist\hos_austa_autorizacao_pre.exe (
    echo [✓] SUCESSO! Executável gerado em:
    echo     %CD%\dist\hos_austa_autorizacao_pre.exe
    echo.
    echo [!] PRÓXIMOS PASSOS:
    echo     1. Copie o arquivo EXE e a pasta 'dist' para um local permanente
    echo     2. Configure o agendador de tarefas do Windows (veja AGENDAR.md)
    echo.
) else (
    echo [X] ERRO ao gerar executável. Verifique os logs acima.
)

pause
