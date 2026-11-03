param([switch]$Enable)
$ErrorActionPreference = 'Stop'
$taskBotRoot = $PSScriptRoot
$taskBotPython = (Get-Command python -ErrorAction Stop).Source
$taskBotName = 'TaiwanDSJobBot'
if (Get-ScheduledTask -TaskName $taskBotName -ErrorAction SilentlyContinue) {
    throw 'TaiwanDSJobBot already exists and was not changed. Inspect it before updating.'
}
if ($Enable) {
    # Verify a real run before enabling unattended search. The launcher reads .env.
    & $taskBotPython -X utf8 (Join-Path $taskBotRoot 'run_local.py') --preview
    if ($LASTEXITCODE -ne 0) { throw 'Search preview failed; the daily task was not enabled.' }
}
$taskBotLauncher = Join-Path $taskBotRoot 'run_local.py'
$taskBotAction = New-ScheduledTaskAction -Execute $taskBotPython -Argument ('-X utf8 "' + $taskBotLauncher + '" --scheduled') -WorkingDirectory $taskBotRoot
$taskBotTrigger = New-ScheduledTaskTrigger -Daily -At '09:00'
$taskBotSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45)
$taskBotDefinition = New-ScheduledTask -Action $taskBotAction -Trigger $taskBotTrigger -Settings $taskBotSettings -Description 'Taiwan DS new-graduate vacancies; local Python deployment.'
$taskBotDefinition.Settings.Enabled = [bool]$Enable
Register-ScheduledTask -TaskName $taskBotName -InputObject $taskBotDefinition | Select-Object TaskName,State
Write-Output 'Daily trigger follows the Windows system timezone. Keep Windows set to Taipei for 09:00 Taiwan time.'
