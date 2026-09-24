$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Register-DI {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Script,
    [Parameter(Mandatory=$true)]$Triggers
  )

  # Idempotent: remove any prior version first.
  $existing = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if ($existing) { Unregister-ScheduledTask -TaskName $Name -Confirm:$false }

  $action    = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$root\scripts\$Script`"" `
    -WorkingDirectory $root

  $principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U -RunLevel Limited

  $settings  = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -Compatibility "Win8"

  Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Triggers `
    -Principal $principal -Settings $settings | Out-Null
  Write-Host "registered: $Name"
}

$now = Get-Date

# every 30 min (from now)
$t_feeds = New-ScheduledTaskTrigger -Once -At $now `
  -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration ([TimeSpan]::MaxValue)

# every 60 min
$t_yt = New-ScheduledTaskTrigger -Once -At $now `
  -RepetitionInterval (New-TimeSpan -Minutes 60) -RepetitionDuration ([TimeSpan]::MaxValue)

# every 15 min
$t_imp = New-ScheduledTaskTrigger -Once -At $now `
  -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration ([TimeSpan]::MaxValue)

# daily times
$t_gsc     = New-ScheduledTaskTrigger -Daily -At ([DateTime]"04:00")
$t_backup  = New-ScheduledTaskTrigger -Daily -At ([DateTime]"03:00")
$t_dbstats = New-ScheduledTaskTrigger -Daily -At ([DateTime]"06:00")
# Sunday 03:30
$t_vac = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At ([DateTime]"03:30")

Register-DI -Name "DiscoverIntel_Feeds"          -Script "run-feeds.ps1"           -Triggers $t_feeds
Register-DI -Name "DiscoverIntel_YouTube"        -Script "run-youtube.ps1"         -Triggers $t_yt
Register-DI -Name "DiscoverIntel_ImportDiscover" -Script "run-import-discover.ps1" -Triggers $t_imp
Register-DI -Name "DiscoverIntel_GSC"            -Script "run-gsc.ps1"             -Triggers $t_gsc
Register-DI -Name "DiscoverIntel_Backup"         -Script "run-backup.ps1"          -Triggers $t_backup
Register-DI -Name "DiscoverIntel_Vacuum"         -Script "run-vacuum.ps1"          -Triggers $t_vac
Register-DI -Name "DiscoverIntel_DBStats"        -Script "run-dbstats.ps1"         -Triggers $t_dbstats

# ---- Sprint 2 additions ----

# 2-hour cadence tasks, staggered by 15 min so resolver -> matcher -> tagger
# proceeds in order (Task Scheduler doesn't do dependencies natively).
$t_resolve = New-ScheduledTaskTrigger -Once -At $now `
  -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration ([TimeSpan]::MaxValue)
$t_match = New-ScheduledTaskTrigger -Once -At ($now.AddMinutes(15)) `
  -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration ([TimeSpan]::MaxValue)
$t_tag = New-ScheduledTaskTrigger -Once -At ($now.AddMinutes(30)) `
  -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration ([TimeSpan]::MaxValue)
# TOI GA daily at 04:30 (after ET GSC at 04:00)
$t_toi = New-ScheduledTaskTrigger -Daily -At ([DateTime]"04:30")

Register-DI -Name "DiscoverIntel_ResolveUrls"   -Script "run-resolve-urls.ps1"   -Triggers $t_resolve
Register-DI -Name "DiscoverIntel_MatchOutcomes" -Script "run-match-outcomes.ps1" -Triggers $t_match
Register-DI -Name "DiscoverIntel_TagEntities"   -Script "run-tag-entities.ps1"   -Triggers $t_tag
Register-DI -Name "DiscoverIntel_ToiGa"         -Script "run-toi-ga.ps1"         -Triggers $t_toi

# ---- Sprint 3 additions ----

# BuildTopicStats: every 2h at +45 min offset from Sprint 2's resolver (:00)
$t_bts = New-ScheduledTaskTrigger -Once -At ($now.AddMinutes(45)) `
  -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration ([TimeSpan]::MaxValue)
# TOS: every 2h at +60 min offset (top of next hour)
$t_tos = New-ScheduledTaskTrigger -Once -At ($now.AddMinutes(60)) `
  -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration ([TimeSpan]::MaxValue)
# Digest: twice daily at 11:00 UTC and 17:00 UTC
$t_digest_11 = New-ScheduledTaskTrigger -Daily -At ([DateTime]::SpecifyKind([DateTime]"11:00", [DateTimeKind]::Utc)).ToLocalTime()
$t_digest_17 = New-ScheduledTaskTrigger -Daily -At ([DateTime]::SpecifyKind([DateTime]"17:00", [DateTimeKind]::Utc)).ToLocalTime()

Register-DI -Name "DiscoverIntel_BuildTopicStats" -Script "run-build-topic-stats.ps1" -Triggers $t_bts
Register-DI -Name "DiscoverIntel_TOS"             -Script "run-tos.ps1"               -Triggers $t_tos
Register-DI -Name "DiscoverIntel_Digest"          -Script "run-digest.ps1"            -Triggers @($t_digest_11, $t_digest_17)

Write-Host ""
Write-Host "Task Scheduler summary:"
Get-ScheduledTask -TaskName "DiscoverIntel_*" | Format-Table TaskName, State
