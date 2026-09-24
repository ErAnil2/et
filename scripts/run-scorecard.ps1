$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\scorecard.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel scorecard `
      --db "$root\data\warehouse.db" `
      --market "US" `
      --out "$root\data\scorecards" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] scorecard exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] scorecard wrapper-error: $_" | Add-Content $log
  exit 1
}
