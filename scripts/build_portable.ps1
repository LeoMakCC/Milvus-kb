$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

.\.venv\Scripts\python.exe -m PyInstaller `
    --clean `
    --noconfirm `
    "build\pyinstaller\KnowledgeQA.spec"

Copy-Item -Force "docker-compose.yml" "dist\KnowledgeQA\docker-compose.yml"
Copy-Item -Force "README.md" "dist\KnowledgeQA\README.md"

Write-Output "portable_dir=dist\KnowledgeQA"
