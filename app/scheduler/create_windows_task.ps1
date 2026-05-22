$TaskName = "Flow Map Brasil - Relatorio Semanal"
$ProjectPath = "C:\flow-map-brasil"
$BatPath = "$ProjectPath\app\scheduler\run_weekly_report.bat"

$Action = New-ScheduledTaskAction -Execute $BatPath
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 8:00AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Gera e envia o PDF semanal do Flow Map Brasil pelo Telegram" -Force
