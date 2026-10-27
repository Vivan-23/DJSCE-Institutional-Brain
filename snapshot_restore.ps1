# Replace this machine's data with a snapshot made by snapshot_export.ps1.
# WARNING: overwrites the local Postgres, Neo4j and Chroma data.
# Usage: ./snapshot_restore.ps1 -Snapshot <path\to\djsce-brain-snapshot-*.zip> [-Yes]
param(
    [Parameter(Mandatory = $true)][string]$Snapshot,
    [switch]$Yes
)
$ErrorActionPreference = "Stop"
$volumes = @("pgdata", "neo4jdata", "chromadata")
$project = "djsce-brain"

if (-not (Test-Path $Snapshot)) { throw "Snapshot not found: $Snapshot" }
if (-not $Yes) {
    $answer = Read-Host "This replaces ALL local data with the snapshot. Type yes to continue"
    if ($answer -ne "yes") { Write-Host "Cancelled."; exit 1 }
}

$work = Join-Path $env:TEMP ("djsce-brain-restore-" + (Get-Date -Format "yyyyMMddHHmmss"))
Expand-Archive -Path $Snapshot -DestinationPath $work
try {
    Get-Content (Join-Path $work "manifest.txt") | Write-Host

    # Stop and remove containers (volumes are kept, then overwritten below).
    docker compose down | Out-Null
    foreach ($v in $volumes) {
        Write-Host "Restoring $v..."
        # Compose's labels, so `docker compose up` adopts the volume without a warning.
        docker volume create --label "com.docker.compose.project=$project" --label "com.docker.compose.volume=$v" "${project}_${v}" | Out-Null
        docker run --rm -v "${project}_${v}:/v" -v "${work}:/in:ro" alpine sh -c "find /v -mindepth 1 -delete && tar xzf /in/$v.tgz -C /v"
        if ($LASTEXITCODE -ne 0) { throw "Restoring $v failed" }
    }
}
finally {
    Remove-Item -Recurse -Force $work
}
Write-Host "Done. Start the app with: docker compose up -d --build"
