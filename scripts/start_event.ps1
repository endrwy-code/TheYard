# The Yard - start_event.ps1
# Opens the three windows you need: web, bot, tunnel.
# Run it from the project folder:   .\scripts\start_event.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

Write-Host ""
Write-Host "  THE YARD - event day start" -ForegroundColor Yellow
Write-Host "  Project folder: $root"
Write-Host ""

# --- checks before we open anything -------------------------------------
if (-not (Test-Path ".\venv\Scripts\activate")) {
    Write-Host "  No venv found in this folder. Are you in C:\Users\endrw\my-mini-app ?" -ForegroundColor Red
    Read-Host "  Press Enter to close"; exit 1
}
if (-not (Test-Path ".\.env")) {
    Write-Host "  No .env found. Copy .env.example to .env and fill it in (RUNBOOK phase 4)." -ForegroundColor Red
    Read-Host "  Press Enter to close"; exit 1
}
if (-not (Test-Path ".\data\app.db")) {
    Write-Host "  No database yet. Run:  python manage.py init-db   (RUNBOOK phase 5)" -ForegroundColor Red
    Read-Host "  Press Enter to close"; exit 1
}

$busy = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "  Port 5000 is already in use by process $($busy[0].OwningProcess)." -ForegroundColor Red
    Write-Host "  An old app.py is probably still running. Close it, or:"
    Write-Host "     Stop-Process -Id $($busy[0].OwningProcess)"
    Read-Host "  Press Enter to close"; exit 1
}

# --- which tunnel? ------------------------------------------------------
Write-Host "  Which tunnel?"
Write-Host "    1  Tailscale Funnel   (event day - fixed address, no warning page)"
Write-Host "    2  ngrok              (development / fallback)"
Write-Host "    3  None               (local only, Telegram will not reach it)"
Write-Host ""
$choice = Read-Host "  Type 1, 2 or 3"

switch ($choice) {
    "1" { $tunnelCmd = "tailscale funnel 5000"; $tunnelName = "TUNNEL - Tailscale Funnel" }
    "2" { $tunnelCmd = "ngrok http 5000";       $tunnelName = "TUNNEL - ngrok" }
    "3" { $tunnelCmd = $null;                   $tunnelName = $null }
    default {
        Write-Host "  Not 1, 2 or 3. Nothing started." -ForegroundColor Red
        Read-Host "  Press Enter to close"; exit 1
    }
}

function Start-Window($title, $command) {
    $inner = "`$host.UI.RawUI.WindowTitle = '$title'; Set-Location '$root'; .\venv\Scripts\activate; Write-Host '--- $title ---' -ForegroundColor Cyan; $command"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $inner
}

# --- window 1: the web app ---------------------------------------------
# 24 threads: every open console keeps one for its live updates.
Start-Window "WEB - waitress" "waitress-serve --threads=24 --listen=127.0.0.1:5000 app:app"
Start-Sleep -Seconds 3

# --- window 2: the bot -------------------------------------------------
Start-Window "BOT - long polling" "python bot.py"
Start-Sleep -Seconds 2

# --- window 3: the tunnel ----------------------------------------------
if ($tunnelCmd) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command",
        "`$host.UI.RawUI.WindowTitle = '$tunnelName'; Write-Host '--- $tunnelName ---' -ForegroundColor Cyan; $tunnelCmd"
}

Write-Host ""
Write-Host "  Three windows opening. Now check, in order:" -ForegroundColor Green
Write-Host "    1. WEB window says it is serving on 127.0.0.1:5000"
Write-Host "    2. BOT window says 'Bot started, polling'"
if ($tunnelCmd) {
    Write-Host "    3. TUNNEL window shows a public https:// address"
    Write-Host ""
    Write-Host "  If that address is NOT the one in .env as PUBLIC_URL:"
    Write-Host "    - update PUBLIC_URL in .env"
    Write-Host "    - close and restart the BOT window (it sets the menu button)"
    Write-Host "    - update the Mini App URL in BotFather"
}
Write-Host ""
Write-Host "  Then: http://localhost:5000/admin  ->  sign in  ->  check Overview loads."
Write-Host "  Then: open the public URL on your phone with wifi OFF."
Write-Host ""
Read-Host "  Press Enter to close this window (the three stay open)"
