$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\import-discover.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel import-discover `
      --db "$root\data\warehouse.db" `
      --watch `
      --imports-dir "$root\data\imports\discover" `
      --config-dir "$root\config" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] import-discover exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] import-discover wrapper-error: $_" | Add-Content $log
  exit 1
}
