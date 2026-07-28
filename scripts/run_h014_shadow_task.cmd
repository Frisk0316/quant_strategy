@echo off
rem H-014 daily shadow cycle (ADR-0011): top-up DVOL + 1m candles, run one
rem shadow cycle, refresh the bias report. User-approved scheduled task
rem 2026-07-15; remove with: schtasks /Delete /TN quant_h014_shadow_daily /F
rem 2026-07-28 (user request): desktop toasts identify this window and signal
rem when it is safe to shut down; see scripts\h014_shadow_notify.ps1.
title H-014 Shadow Cycle (ADR-0011) - do not shut down, ~10 min
cd /d C:\quant_strategy
if not exist logs mkdir logs
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\h014_shadow_notify.ps1 -Phase start
"C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe" research\probes\h014_daily_shadow_ops.py --no-wait >> logs\h014_shadow_daily.log 2>&1
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\h014_shadow_notify.ps1 -Phase fail
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\h014_shadow_notify.ps1 -Phase ok
)
