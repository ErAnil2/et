$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\build-topic-stats.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel build-topic-stats `
      --db "$root\data\warehouse.db" `
      --window-hours 72 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] build-topic-stats exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] build-topic-stats wrapper-error: $_" | Add-Content $log
  exit 1
}
