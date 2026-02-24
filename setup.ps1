# Script PowerShell para configurar o ambiente de desenvolvimento
# Uso: execute no PowerShell na raiz do projeto

param(
    [switch]$InstallRequirements
)

Write-Host "Criando ambiente virtual (.venv) se não existir..."
if (-not (Test-Path .\.venv)) {
    python -m venv .venv
}

Write-Host "Ativando venv..."
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\.venv\Scripts\Activate.ps1

if ($InstallRequirements) {
    Write-Host "Atualizando pip e instalando dependências..."
    python -m pip install --upgrade pip
    pip install -r requirements.txt
} else {
    Write-Host "Passo de instalação de dependências pulado. Use -InstallRequirements para instalar." 
}

Write-Host "Setup concluído. Use: . .\.venv\Scripts\Activate.ps1 para ativar o venv no futuro."