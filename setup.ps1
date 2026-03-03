# Script PowerShell para configurar o ambiente de desenvolvimento
# Uso: execute no PowerShell na raiz do projeto

Write-Host "Criando ambiente virtual (.venv) se nao existir..."
if (-not (Test-Path .\.venv)) {
    python -m venv .venv
}

Write-Host "Ativando venv..."
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\.venv\Scripts\Activate.ps1

Write-Host "Atualizando pip e instalando dependencias..."
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host "Setup concluido. Use: . .\.venv\Scripts\Activate.ps1 para ativar o venv no futuro."