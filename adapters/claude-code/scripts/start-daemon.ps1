# scripts/start-daemon.ps1
# Maimai session persistence - daemon startup script

$SessionName = "maimai-talent"
$ProfilePath = "$env:USERPROFILE\.agent-browser\maimai-profile"
$KeyPath = "$env:USERPROFILE\.agent-browser\maimai-key"

# Ensure profile directory exists
if (-not (Test-Path $ProfilePath)) {
    New-Item -ItemType Directory -Path $ProfilePath -Force | Out-Null
    Write-Host "Created profile directory: $ProfilePath" -ForegroundColor Yellow
}

# Generate encryption key if not exists
if (-not (Test-Path $KeyPath)) {
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    $bytes = New-Object byte[] 32
    $rng.GetBytes($bytes)
    $key = [BitConverter]::ToString($bytes).Replace("-", "").ToLower()
    $key | Out-File -FilePath $KeyPath -Encoding utf8 -NoNewline
    icacls $KeyPath /inheritance:r /grant:r "$env:USERNAME:R" 2>&1 | Out-Null
    Write-Host "Generated new encryption key at $KeyPath" -ForegroundColor Yellow
}

# Set environment variables
$env:AGENT_BROWSER_ENCRYPTION_KEY = Get-Content $KeyPath
$env:AGENT_BROWSER_SESSION_NAME = $SessionName
$env:AGENT_BROWSER_HEADED = "1"

Write-Host "Session persistence configured:" -ForegroundColor Cyan
Write-Host "  Profile: $ProfilePath" -ForegroundColor Gray
Write-Host "  Session: $SessionName" -ForegroundColor Gray

# Start browser with persistent profile
Write-Host "Opening browser..." -ForegroundColor Cyan
agent-browser --profile $ProfilePath --session-name $SessionName --headed open "https://maimai.cn"

Write-Host "Browser session ended" -ForegroundColor Gray
