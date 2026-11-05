# Registers (or removes) a Windows scheduled task that runs the AICL night shift every night.
#   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1            # every night at 02:00
#   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1 -At 03:30  # another time
#   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1 -Remove    # undo
# The task runs as you, only while you are signed in, wakes the PC from sleep if wake timers are
# allowed in Power Options, starts late if the PC was off at the set time, and stops after 3 hours.
param([string]$At = "02:00", [switch]$Remove)
$name = "AICL night shift"
if ($Remove) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "removed: $name"
    exit 0
}
$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python -ErrorAction Stop).Source
$action = New-ScheduledTaskAction -Execute $python -Argument "-X utf8 examples\night_shift.py" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force `
    -Description "AICL autonomous network: works through out\night\inbox and writes out\night\<date>\REPORT.md" | Out-Null
Write-Output "registered: $name, every day at $At, in $root"
Write-Output "check:  Get-ScheduledTask -TaskName '$name' | Get-ScheduledTaskInfo"
Write-Output "undo:   powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1 -Remove"
