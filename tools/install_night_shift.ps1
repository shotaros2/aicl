# Registers (or removes) the Windows scheduled tasks that let the AICL team work without being started:
#   "AICL night shift"  every night at 02:00: the inbox, then the scout's own proposals (--mode night).
#                       Wakes the PC from sleep if wake timers are allowed in Power Options.
#   "AICL inbox check"  every 30 minutes while the PC is awake: only the inbox (--mode inbox), so a task
#                       you drop into out\night\inbox (for example from your phone through OneDrive)
#                       starts soon. Exits at once when the inbox is empty; costs nothing then.
# Both run as you, only while you are signed in, never two at a time (a lock file), and stop after 3 hours.
#   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1             # install both
#   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1 -At 03:30   # another night time
#   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1 -NoInbox    # night shift only
#   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1 -Remove     # undo both
param([string]$At = "02:00", [switch]$NoInbox, [switch]$Remove)
$night = "AICL night shift"
$inbox = "AICL inbox check"
if ($Remove) {
    foreach ($n in @($night, $inbox)) { Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue }
    Write-Output "removed: $night, $inbox"
    exit 0
}
$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python -ErrorAction Stop).Source
$limit = New-TimeSpan -Hours 3

$a1 = New-ScheduledTaskAction -Execute $python -Argument "-X utf8 examples\night_shift.py --mode night" -WorkingDirectory $root
$t1 = New-ScheduledTaskTrigger -Daily -At $At
$s1 = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit $limit -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $night -Action $a1 -Trigger $t1 -Settings $s1 -Force `
    -Description "AICL: inbox tasks, then the scout's own proposals; report in out\night\<date>\REPORT.md" | Out-Null
Write-Output "registered: $night, every day at $At"

if (-not $NoInbox) {
    $a2 = New-ScheduledTaskAction -Execute $python -Argument "-X utf8 examples\night_shift.py --mode inbox" -WorkingDirectory $root
    $t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 30) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
    $s2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit $limit `
        -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $inbox -Action $a2 -Trigger $t2 -Settings $s2 -Force `
        -Description "AICL: every 30 minutes, run any task waiting in out\night\inbox" | Out-Null
    Write-Output "registered: $inbox, every 30 minutes while the PC is awake"
}
Write-Output "folder: $root"
Write-Output "check:  Get-ScheduledTask -TaskName 'AICL*' | Get-ScheduledTaskInfo"
Write-Output "undo:   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1 -Remove"
