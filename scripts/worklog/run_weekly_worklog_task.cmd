@echo off
rem Weekly worklog generator: runs headless Claude every Sunday evening.
rem Registered as scheduled task quant_weekly_worklog (SUN 21:07 local).
cd /d C:\quant_strategy
if not exist logs mkdir logs
echo ===== %date% %time% weekly worklog run ===== >> logs\weekly_worklog.log
type scripts\worklog\weekly_worklog_prompt.md | "C:\Users\woody\AppData\Roaming\npm\claude.cmd" -p --model sonnet --allowedTools "Bash,Read,Write,Edit,Glob,Grep" >> logs\weekly_worklog.log 2>&1
echo ===== exit %errorlevel% ===== >> logs\weekly_worklog.log
