# Runs the full evaluation against the running stack and prints the results summary.
# Prerequisite: docker compose up -d --build; python ingest_institutional.py --approve
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose --profile eval run --rm evaluator
Write-Host "`nResults written to publication/01_ipd_report/results/RESULTS.md" -ForegroundColor Green
