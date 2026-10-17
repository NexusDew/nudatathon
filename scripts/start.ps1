# Запуск сервиса одной командой: llama-server (VLM) + API.
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1 [-Model 4b|8b] [-Port 8000]
param(
    [ValidateSet("4b", "8b")] [string]$Model = "8b",
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Weights = if ($env:WEIGHTS_DIR) { $env:WEIGHTS_DIR } else { "D:/nudatathon_weights" }
$Name = if ($Model -eq "8b") { "8B" } else { "4B" }
$Gguf = "$Weights/qwen3vl-$Model/Qwen3VL-$Name-Instruct-Q4_K_M.gguf"
$Mmproj = "$Weights/qwen3vl-$Model/mmproj-Qwen3VL-$Name-Instruct-Q8_0.gguf"
foreach ($f in @($Gguf, $Mmproj)) { if (-not (Test-Path $f)) { throw "Нет файла модели: $f (scripts/download_weights.py)" } }

# 1. VLM-сервер (только localhost)
$llama = Get-Process llama-server -ErrorAction SilentlyContinue
if (-not $llama) {
    Write-Host "Запуск llama-server ($Name)..."
    Start-Process -FilePath "$Root\weights\llama.cpp\llama-server.exe" -WindowStyle Minimized -ArgumentList @(
        # 4 слота = 4 параллельных запроса одним батчем (VLM_PARALLEL в пайплайне), 2048 токенов на слот
        "-m", $Gguf, "--mmproj", $Mmproj, "-ngl", "99", "-c", "8192", "-np", "4", "-fa", "on",
        "--host", "127.0.0.1", "--port", "8080"
    )
}
for ($i = 0; $i -lt 120; $i++) {
    try { if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}
    Start-Sleep -Seconds 1
}
Write-Host "llama-server готов"

# 2. API + UI
$env:PIPELINE_MODE = "real"
$env:WEIGHTS_DIR = $Weights
# Только localhost: наружу сервис выходит через туннель (scripts\tunnel_ngrok.ps1), а не в общую Wi-Fi сеть
& "$Root\.venv\Scripts\python.exe" -m uvicorn service.app:app --host 127.0.0.1 --port $Port
