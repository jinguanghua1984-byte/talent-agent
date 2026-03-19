# scripts/check-session.ps1
# Maimai session persistence - session status check script

$SessionName = "maimai-talent"
$ProfilePath = "$env:USERPROFILE\.agent-browser\maimai-profile"

Write-Host "Checking session persistence..." -ForegroundColor Cyan

# Check if profile exists
if (Test-Path $ProfilePath) {
    Write-Host "Profile: exists" -ForegroundColor Green
    
    # Check for cookies file
    $cookiesPath = Join-Path $ProfilePath "Default/Cookies"
    if (Test-Path $cookiesPath) {
        Write-Host "Cookies: saved" -ForegroundColor Green
        Write-Host "Login state: persisted (may need refresh)" -ForegroundColor Yellow
    } else {
        Write-Host "Cookies: not found" -ForegroundColor Yellow
        Write-Host "Login state: not logged in" -ForegroundColor Red
    }
    exit 0
} else {
    Write-Host "Profile: not found" -ForegroundColor Red
    Write-Host "Run .\scripts\start-daemon.ps1 to create" -ForegroundColor Yellow
    exit 1
}
