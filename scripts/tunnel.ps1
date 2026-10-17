# Публичный URL для жюри через Cloudflare quick tunnel (без аккаунта).
#   powershell -ExecutionPolicy Bypass -File scripts\tunnel.ps1 [-Port 8000]
# ВАЖНО: адрес *.trycloudflare.com меняется при каждом перезапуске туннеля — после сдачи не перезапускать.
param([int]$Port = 8000)
$Root = Split-Path -Parent $PSScriptRoot
$Exe = "$Root\weights\cloudflared\cloudflared.exe"
if (-not (Test-Path $Exe)) { throw "Нет $Exe — скачать: https://github.com/cloudflare/cloudflared/releases" }
try { Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/health" -TimeoutSec 3 | Out-Null }
catch { throw "Сервис не отвечает на :$Port — сначала scripts\start.ps1" }
Write-Host "Туннель на http://127.0.0.1:$Port ... адрес появится строкой https://<...>.trycloudflare.com"
& $Exe tunnel --no-autoupdate --url "http://127.0.0.1:$Port"
