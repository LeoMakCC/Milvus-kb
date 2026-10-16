$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:KB_PORT = "8788"

$out = Join-Path $root "data\logs\desktop-8788.out.log"
$err = Join-Path $root "data\logs\desktop-8788.err.log"

$process = Start-Process `
    -FilePath (Join-Path $root ".venv\Scripts\python.exe") `
    -ArgumentList "-m", "knowledgeqa.desktop" `
    -WorkingDirectory $root `
    -WindowStyle Normal `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -PassThru

Write-Output "started_pid=$($process.Id)"
