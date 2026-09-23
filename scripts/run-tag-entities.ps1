$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\tag-entities.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel tag-entities `
      --db "$root\data\warehouse.db" `
      --source both `
      --limit 5000 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] tag-entities exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] tag-entities wrapper-error: $_" | Add-Content $log
  exit 1
}
