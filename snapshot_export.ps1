# Export the live data (Postgres + Neo4j + Chroma volumes) into one zip, to hand to a teammate.
# The zip holds real staff data and password hashes: share it privately, NEVER commit it to git.
# Usage: ./snapshot_export.ps1 [-OutDir <folder>]
param(
    [string]$OutDir = "$HOME\Documents\djsce-brain-private\snapshots"
)
$ErrorActionPreference = "Stop"
$volumes = @("pgdata", "neo4jdata", "chromadata")
$project = "djsce-brain"

# Databases must be stopped for a consistent copy; restart them afterwards if they were up.
$running = docker compose ps -q
if ($running) {
    Write-Host "Stopping the stack for a consistent copy..."
    docker compose stop | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$name = "djsce-brain-snapshot-$stamp"
$work = Join-Path $env:TEMP $name
New-Item -ItemType Directory -Force $work | Out-Null
New-Item -ItemType Directory -Force $OutDir | Out-Null

try {
    foreach ($v in $volumes) {
        Write-Host "Copying $v..."
        docker run --rm -v "${project}_${v}:/v:ro" -v "${work}:/out" alpine tar czf "/out/$v.tgz" -C /v .
        if ($LASTEXITCODE -ne 0) { throw "Copying $v failed" }
    }
    @(
        "created: $(Get-Date -Format s)"
        "git_commit: $(git rev-parse --short HEAD)"
        "volumes: $($volumes -join ', ')"
    ) | Set-Content -Encoding utf8 (Join-Path $work "manifest.txt")

    $zip = Join-Path $OutDir "$name.zip"
    Compress-Archive -Path "$work\*" -DestinationPath $zip -Force
    Write-Host "Snapshot written: $zip"
    Write-Host "Share it privately (Drive/WhatsApp/pen drive) - not through git."
}
finally {
    Remove-Item -Recurse -Force $work
    if ($running) {
        Write-Host "Restarting the stack..."
        docker compose start | Out-Null
    }
}
