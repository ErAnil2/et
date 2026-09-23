$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\match-outcomes.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel match-outcomes `
      --db "$root\data\warehouse.db" `
      --since 72 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] match-outcomes exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] match-outcomes wrapper-error: $_" | Add-Content $log
  exit 1
}
