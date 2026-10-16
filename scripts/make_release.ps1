$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& "$PSScriptRoot\build_portable.ps1"

$archive = Join-Path $root "dist\KnowledgeQA-portable.zip"
if (Test-Path $archive) {
    Remove-Item -LiteralPath $archive -Force
}
Compress-Archive -Path "dist\KnowledgeQA\*" -DestinationPath $archive -Force

$hash = & ".\.venv\Scripts\python.exe" `
    "scripts\release_manifest.py" `
    $archive `
    "dist\manifest.json"

Set-Content `
    -LiteralPath "dist\KnowledgeQA-portable.zip.sha256" `
    -Value "$hash  KnowledgeQA-portable.zip" `
    -Encoding ascii

Write-Output "archive=$archive"
Write-Output "sha256=$hash"
