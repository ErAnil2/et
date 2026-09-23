$ErrorActionPreference = "Continue"
$names = @(
  "DiscoverIntel_Feeds", "DiscoverIntel_YouTube", "DiscoverIntel_ImportDiscover",
  "DiscoverIntel_GSC", "DiscoverIntel_Backup", "DiscoverIntel_Vacuum",
  "DiscoverIntel_DBStats"
)
foreach ($n in $names) {
  $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
  if ($t) {
    Unregister-ScheduledTask -TaskName $n -Confirm:$false
    Write-Host "unregistered: $n"
  } else {
    Write-Host "not present: $n"
  }
}
