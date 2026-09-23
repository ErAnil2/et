$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\resolve-urls.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel resolve-urls `
      --db "$root\data\warehouse.db" `
      --limit 500 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] resolve-urls exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] resolve-urls wrapper-error: $_" | Add-Content $log
  exit 1
}
