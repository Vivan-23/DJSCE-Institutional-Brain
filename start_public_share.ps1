# ==============================================================================
# DJSCE Institutional Brain — Public Sharing & Tunnel Launcher
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  DJSCE INSTITUTIONAL BRAIN -- PUBLIC TUNNEL LAUNCHER             " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Check Docker status
Write-Host "`n[1/5] Checking Docker Compose services..." -ForegroundColor Yellow
docker compose up -d

# 2. Wait for Backend & Frontend Health
Write-Host "`n[2/5] Verifying local service health..." -ForegroundColor Yellow
$backendReady = $false
$maxTries = 15
for ($i = 1; $i -le $maxTries; $i++) {
    try {
        $res = Invoke-RestMethod -Uri "http://localhost:8001/health" -TimeoutSec 2 -ErrorAction Stop
        if ($res.status -eq "ok") {
            $backendReady = $true
            break
        }
    } catch {
        Write-Host "  ... waiting for FastAPI backend ($i/$maxTries)" -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $backendReady) {
    Write-Host "`n[!] Warning: Backend health check timed out. Checking docker status..." -ForegroundColor Red
    docker compose ps
    exit 1
}
Write-Host "  [OK] Backend healthy on http://localhost:8001" -ForegroundColor Green

# 3. Locate and verify ngrok
Write-Host "`n[3/5] Checking ngrok installation..." -ForegroundColor Yellow
$ngrokCmd = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrokCmd) {
    Write-Host "[X] Error: ngrok executable not found in PATH." -ForegroundColor Red
    Write-Host "    Install ngrok or add it to your PATH." -ForegroundColor Yellow
    exit 1
}
Write-Host "  [OK] Found ngrok: $($ngrokCmd.Source)" -ForegroundColor Green

# 4. Check or launch ngrok tunnel
Write-Host "`n[4/5] Checking active ngrok tunnel..." -ForegroundColor Yellow
$publicUrl = $null
try {
    $tunnels = (Invoke-RestMethod -Uri "http://localhost:4040/api/tunnels" -ErrorAction Stop).tunnels
    if ($tunnels.Count -gt 0) {
        $publicUrl = $tunnels[0].public_url
        Write-Host "  [OK] Reusing existing active tunnel: $publicUrl" -ForegroundColor Green
    }
} catch {
    # Not running, start a new background process
    Write-Host "  Starting ngrok tunnel on port 3000..." -ForegroundColor Gray
    Start-Process -FilePath "ngrok" -ArgumentList "http 3000 --log=stdout" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    
    for ($i = 1; $i -le 10; $i++) {
        try {
            $tunnels = (Invoke-RestMethod -Uri "http://localhost:4040/api/tunnels" -ErrorAction Stop).tunnels
            if ($tunnels.Count -gt 0) {
                $publicUrl = $tunnels[0].public_url
                break
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
}

if (-not $publicUrl) {
    Write-Host "`n[X] Error: Failed to retrieve ngrok public URL." -ForegroundColor Red
    Write-Host "    Check if your ngrok authtoken is configured via:" -ForegroundColor Yellow
    Write-Host '    ngrok config add-authtoken YOUR_TOKEN' -ForegroundColor White
    exit 1
}

# 5. Display presentation summary
Write-Host "`n==================================================================" -ForegroundColor Green
Write-Host "  PUBLIC SHARE READY FOR PRESENTATION AND EVALUATION PANEL        " -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "  Shareable Web URL:    $publicUrl" -ForegroundColor Cyan
Write-Host "  Demo Logins:          admin@example.com, aarav.desai@example.com (student) / demo123" -ForegroundColor White
Write-Host "------------------------------------------------------------------" -ForegroundColor Gray
Write-Host "  Architecture:         Single-Domain Reverse Proxy" -ForegroundColor White
Write-Host "                        Next.js proxies /api/* internally to FastAPI" -ForegroundColor Gray
Write-Host "                        (Zero CORS issues, works on free 1-tunnel plans)" -ForegroundColor Gray
Write-Host "  Local Frontend:       http://localhost:3000" -ForegroundColor Gray
Write-Host "  Local Backend:        http://localhost:8001" -ForegroundColor Gray
Write-Host "  Database Isolation:   Postgres (5432), Neo4j (7474), Redis (6379), Chroma (8002)" -ForegroundColor Gray
Write-Host "                        are NOT exposed to the public internet." -ForegroundColor Gray
Write-Host "------------------------------------------------------------------" -ForegroundColor Gray
Write-Host "  To stop the tunnel:   Stop-Process -Name ngrok -ErrorAction SilentlyContinue" -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Green
Write-Host ""
