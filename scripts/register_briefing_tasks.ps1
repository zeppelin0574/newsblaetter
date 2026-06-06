$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot

& (Join-Path $ScriptDir "register_windows_task.ps1") `
    -TaskName "NewsblaetteMorningBriefing" `
    -Time "07:30" `
    -ScriptName "run_morning.ps1"

& (Join-Path $ScriptDir "register_windows_task.ps1") `
    -TaskName "NewsblaetteEveningBriefing" `
    -Time "22:00" `
    -ScriptName "run_evening.ps1"

$legacyTask = Get-ScheduledTask -TaskName "NewsblaetteDailyBriefing" -ErrorAction SilentlyContinue
if ($legacyTask) {
    Disable-ScheduledTask -TaskName "NewsblaetteDailyBriefing" | Out-Null
    Write-Host "Disabled legacy task 'NewsblaetteDailyBriefing' to avoid duplicate morning pushes."
}
