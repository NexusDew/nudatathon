# Публичный URL для жюри через ngrok с постоянным доменом (адрес не меняется при перезапуске).
#   powershell -ExecutionPolicy Bypass -File scripts\tunnel_ngrok.ps1 [-Port 8000]
# Authtoken хранится в локальном конфиге ngrok (%LOCALAPPDATA%\ngrok\ngrok.yml), не в репозитории:
#   weights\ngrok\ngrok.exe config add-authtoken <TOKEN>
param(
    [int]$Port = 8000,
    [string]$Domain = $(if ($env:NGROK_DOMAIN) { $env:NGROK_DOMAIN } else { "fiddling-uncheck-decency.ngrok-free.dev" })
)
$Root = Split-Path -Parent $PSScriptRoot
$Exe = "$Root\weights\ngrok\ngrok.exe"
if (-not (Test-Path $Exe)) { throw "Нет $Exe — скачать: https://ngrok.com/download" }
try { Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/health" -TimeoutSec 3 | Out-Null }
catch { throw "Сервис не отвечает на :$Port — сначала scripts\start.ps1" }
Write-Host "Публичный адрес: https://$Domain  (UI: /, API: /api/v1/...)"
& $Exe http $Port --url "https://$Domain"
