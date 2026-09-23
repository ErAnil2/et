$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\backup.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel backup `
      --db "$root\data\warehouse.db" `
      --dest-dir "$root\data\backups" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] backup exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] backup wrapper-error: $_" | Add-Content $log
  exit 1
}
