$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\digest.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel digest `
      --db "$root\data\warehouse.db" `
      --top 15 `
      --out "$root\data\digests" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] digest exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] digest wrapper-error: $_" | Add-Content $log
  exit 1
}
