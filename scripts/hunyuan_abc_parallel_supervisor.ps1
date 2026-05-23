param(
  [string]$Root = "data\campaigns\hunyuan-8jd-abc-detail-2026-05-22",
  [string]$Db = "data\talent.db",
  [string]$CdpUrl = "http://127.0.0.1:9888",
  [int]$MaxWorkers = 4,
  [int]$IntervalSeconds = 60
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

function Write-JsonFile($Path, $Value) {
  $dir = Split-Path -Parent $Path
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Append-Log($Message) {
  $path = Join-Path $Root "reports\parallel-supervisor.log"
  $dir = Split-Path -Parent $path
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Add-Content -LiteralPath $path -Encoding UTF8 -Value ("{0} {1}" -f (Get-Date).ToString("s"), $Message)
}

function Get-PackJobCount($PackId) {
  $dir = Join-Path $Root ("raw\detail-live\" + $PackId)
  if (-not (Test-Path -LiteralPath $dir)) { return 0 }
  return @(Get-ChildItem -LiteralPath $dir -Filter "job-*.json" -ErrorAction SilentlyContinue).Count
}

function Read-ProcessFiles {
  $stateDir = Join-Path $Root "state"
  if (-not (Test-Path -LiteralPath $stateDir)) { return @() }
  $items = @()
  foreach ($file in Get-ChildItem -LiteralPath $stateDir -Filter "parallel-*.json" -ErrorAction SilentlyContinue) {
    if ($file.Name -eq "parallel-supervisor-process.json") { continue }
    try {
      $info = Get-Content -LiteralPath $file.FullName -Encoding UTF8 | ConvertFrom-Json
    } catch {
      continue
    }
    if (-not $info.runner_id -or -not $info.packs) { continue }
    $alive = $null -ne (Get-Process -Id $info.pid -ErrorAction SilentlyContinue)
    $stderr = Join-Path $Root ("reports\" + $info.runner_id + "-stderr.log")
    $stderrBytes = if (Test-Path -LiteralPath $stderr) { (Get-Item -LiteralPath $stderr).Length } else { 0 }
    $runState = Join-Path $Root ("state\abc-detail-run-state-" + $info.runner_id + ".json")
    $runStatus = $null
    if (Test-Path -LiteralPath $runState) {
      try {
        $runStatus = (Get-Content -LiteralPath $runState -Encoding UTF8 | ConvertFrom-Json).status
      } catch {
        $runStatus = "unreadable"
      }
    }
    $items += [pscustomobject]@{
      file = $file.FullName
      runner_id = [string]$info.runner_id
      pid = [int]$info.pid
      packs = @($info.packs)
      alive = [bool]$alive
      stderr_bytes = [int64]$stderrBytes
      run_status = $runStatus
    }
  }
  return $items
}

function Stop-ActiveWorkers($Workers) {
  foreach ($worker in $Workers) {
    if ($worker.alive) {
      Stop-Process -Id $worker.pid -Force -ErrorAction SilentlyContinue
    }
  }
}

$packIndexPath = Join-Path $Root "raw\detail-targets\pack-index.json"
$statePath = Join-Path $Root "state\parallel-supervisor-state.json"
$packIndex = Get-Content -LiteralPath $packIndexPath -Encoding UTF8 | ConvertFrom-Json
$packs = @($packIndex.packs)
Append-Log ("started max_workers={0} packs={1}" -f $MaxWorkers, $packs.Count)

while ($true) {
  $workers = @(Read-ProcessFiles)
  $activeWorkers = @($workers | Where-Object { $_.alive })
  $blockedWorkers = @($workers | Where-Object { $_.stderr_bytes -gt 0 -or $_.run_status -eq "stopped" })
  if ($blockedWorkers.Count -gt 0) {
    Stop-ActiveWorkers $activeWorkers
    $state = [pscustomobject]@{
      status = "blocked"
      updated_at = (Get-Date).ToString("s")
      reason = "worker_error_or_stopped"
      blocked_workers = $blockedWorkers
    }
    Write-JsonFile $statePath $state
    Append-Log "blocked worker_error_or_stopped"
    exit 2
  }

  $activePackIds = @{}
  foreach ($worker in $activeWorkers) {
    foreach ($packId in @($worker.packs)) {
      $activePackIds[[string]$packId] = $true
    }
  }

  $completed = @()
  $pending = @()
  foreach ($pack in $packs) {
    $packId = [string]$pack.pack_id
    $jobs = Get-PackJobCount $packId
    if ($jobs -ge [int]$pack.count) {
      $completed += $packId
    } elseif (-not $activePackIds.ContainsKey($packId)) {
      $pending += $pack
    }
  }

  while ($activeWorkers.Count -lt $MaxWorkers -and $pending.Count -gt 0) {
    $pack = $pending[0]
    $pending = @($pending | Select-Object -Skip 1)
    $packId = [string]$pack.pack_id
    $runnerId = "parallel-auto-" + ($packId -replace "detail-abc-pack-", "p")
    $stdout = Join-Path $Root ("reports\" + $runnerId + "-stdout.log")
    $stderr = Join-Path $Root ("reports\" + $runnerId + "-stderr.log")
    $args = @(
      "-m", "scripts.hunyuan_abc_detail_tasks", "run",
      "--campaign-root", $Root,
      "--db", $Db,
      "--cdp-url", $CdpUrl,
      "--delay-seconds", "10",
      "--timeout-seconds", "45",
      "--runner-id", $runnerId,
      "--pack-ids", $packId
    )
    $process = Start-Process -FilePath "python" -ArgumentList $args -WorkingDirectory (Get-Location) -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $processInfo = [pscustomobject]@{
      runner_id = $runnerId
      pid = $process.Id
      packs = @($packId)
      stdout = $stdout
      stderr = $stderr
      started_at = (Get-Date).ToString("s")
    }
    Write-JsonFile (Join-Path $Root ("state\" + $runnerId + "-process.json")) $processInfo
    Append-Log ("launched runner={0} pid={1} pack={2}" -f $runnerId, $process.Id, $packId)
    $activeWorkers = @(Read-ProcessFiles | Where-Object { $_.alive })
  }

  $totalJobs = 0
  foreach ($pack in $packs) {
    $totalJobs += Get-PackJobCount ([string]$pack.pack_id)
  }
  $totalTargets = ($packs | Measure-Object -Property count -Sum).Sum
  $state = [pscustomobject]@{
    status = if ($completed.Count -ge $packs.Count) { "completed" } else { "running" }
    updated_at = (Get-Date).ToString("s")
    max_workers = $MaxWorkers
    active_workers = @(Read-ProcessFiles | Where-Object { $_.alive })
    completed_packs = $completed.Count
    total_packs = $packs.Count
    done_jobs = $totalJobs
    total_jobs = $totalTargets
    percent = [math]::Round($totalJobs * 100.0 / [math]::Max(1, $totalTargets), 2)
  }
  Write-JsonFile $statePath $state
  if ($state.status -eq "completed") {
    Append-Log "completed"
    exit 0
  }
  Start-Sleep -Seconds $IntervalSeconds
}
