$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Missing .venv. Follow README development setup first."
}

.\.venv\Scripts\python.exe -m knowledgeqa.desktop
