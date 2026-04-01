# ============================================================
# sync_tasy_watcher.ps1 — Monitora pasta local e MOVE PDFs
# para o share de rede do TASY instantaneamente.
#
# Uso: powershell -ExecutionPolicy Bypass -File scripts\sync_tasy_watcher.ps1
# ============================================================

$ORIGEM  = Join-Path $PSScriptRoot "..\tasy-storage\anexo_opme"
$DESTINO = "\\172.20.255.13\tasyausta\anexo_opme"

# Garante que a pasta de origem existe
if (-not (Test-Path $ORIGEM)) {
    New-Item -ItemType Directory -Path $ORIGEM -Force | Out-Null
}

Write-Host "[sync_tasy] Monitorando: $ORIGEM"
Write-Host "[sync_tasy] Destino:     $DESTINO"
Write-Host "[sync_tasy] Pressione Ctrl+C para parar."

# Move arquivos que já existem na pasta
Get-ChildItem -Path $ORIGEM -Filter "*.pdf" | ForEach-Object {
    $dest = Join-Path $DESTINO $_.Name
    Move-Item $_.FullName $dest -Force
    Write-Host "[sync_tasy] Movido (existente): $($_.Name)"
}

# Cria watcher para novos arquivos
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $ORIGEM
$watcher.Filter = "*.pdf"
$watcher.EnableRaisingEvents = $true

$action = {
    Start-Sleep -Milliseconds 500  # aguarda escrita terminar
    $path = $Event.SourceEventArgs.FullPath
    $name = $Event.SourceEventArgs.Name
    $dest = Join-Path "\\172.20.255.13\tasyausta\anexo_opme" $name
    try {
        Move-Item $path $dest -Force
        Write-Host "[sync_tasy] Movido: $name -> $dest"
    } catch {
        Write-Host "[sync_tasy] ERRO ao mover ${name}: $_"
    }
}

Register-ObjectEvent $watcher "Created" -Action $action | Out-Null

# Mantém o script rodando
try {
    while ($true) { Start-Sleep 1 }
} finally {
    $watcher.EnableRaisingEvents = $false
    $watcher.Dispose()
}
