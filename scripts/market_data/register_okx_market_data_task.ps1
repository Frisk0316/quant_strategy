#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"
$taskName = "quant_okx_market_data"
$taskUser = "MAXWEL_FRIEDMAN\woody"

Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "C:\Windows\System32\cmd.exe" `
    -Argument "/d /c C:\quant_strategy\scripts\market_data\run_okx_market_data_collector.cmd" `
    -WorkingDirectory "C:\quant_strategy"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal `
    -UserId $taskUser `
    -LogonType S4U `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Public OKX books, trades, and funding collector. No credentials or order path." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
$task = Get-ScheduledTask -TaskName $taskName
if ($task.Principal.LogonType -ne "S4U" -or $task.Principal.RunLevel -ne "Limited") {
    throw "Unexpected task principal: $($task.Principal.LogonType)/$($task.Principal.RunLevel)"
}

$task | Select-Object TaskName, State, Principal, Settings
