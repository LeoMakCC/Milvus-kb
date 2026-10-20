$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist\KnowledgeQA"
$exe = Join-Path $dist "KnowledgeQA.exe"

$env:KB_PORT = "8790"
$process = Start-Process `
    -FilePath $exe `
    -WorkingDirectory $dist `
    -PassThru

Write-Output "started_pid=$($process.Id)"
