$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\youtube.log"
$ts   = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel feeds `
      --db "$root\data\warehouse.db" `
      --kind "youtube" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] youtube exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] youtube wrapper-error: $_" | Add-Content $log
  exit 1
}
