$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist\KnowledgeQA"
$exe = Join-Path $dist "KnowledgeQA.exe"

$env:KB_PORT = "8790"
$process = Start-Process `
    -FilePath $exe `
    -WorkingDirectory $dist `
    -PassThru

try {
    $deadline = (Get-Date).AddSeconds(45)
    $health = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod `
                -Uri "http://127.0.0.1:8790/api/v1/health" `
                -TimeoutSec 2
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $health) {
        throw "Portable app health check timed out"
    }
    $status = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8790/api/v1/status" `
        -TimeoutSec 5
    [PSCustomObject]@{
        Pid = $process.Id
        Health = $health.status
        ApiPort = $status.api_port
        SchemaVersion = $status.db_schema_version
    } | Format-List
} finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
