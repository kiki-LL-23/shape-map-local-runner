param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$scriptPath = Resolve-Path -LiteralPath "$PSScriptRoot\web_app.py"
$wslScript = (wsl --exec wslpath -a "$scriptPath").Trim()

Write-Host "Starting SHAPE-MaP Local Runner..."
Write-Host "Open http://127.0.0.1:$Port in your browser."
wsl --exec python3 "$wslScript" --port "$Port"
