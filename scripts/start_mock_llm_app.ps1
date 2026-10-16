$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:KB_PORT = "8788"
$env:KB_LLM_BASE_URL = "http://127.0.0.1:8899/v1"
$env:KB_LLM_API_KEY = "mock"
$env:KB_LLM_MODEL = "mock"

$out = Join-Path $root "data\logs\desktop-m4b1.out.log"
$err = Join-Path $root "data\logs\desktop-m4b1.err.log"

$process = Start-Process `
    -FilePath (Join-Path $root ".venv\Scripts\python.exe") `
    -ArgumentList "-m", "knowledgeqa.desktop" `
    -WorkingDirectory $root `
    -WindowStyle Normal `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -PassThru

Write-Output "started_pid=$($process.Id)"
