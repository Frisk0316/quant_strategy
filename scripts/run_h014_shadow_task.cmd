@echo off
rem H-014 daily shadow cycle (ADR-0011): top-up DVOL + 1m candles, run one
rem shadow cycle, refresh the bias report. User-approved scheduled task
rem 2026-07-15; remove with: schtasks /Delete /TN quant_h014_shadow_daily /F
cd /d C:\quant_strategy
if not exist logs mkdir logs
"C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe" research\probes\h014_daily_shadow_ops.py --no-wait >> logs\h014_shadow_daily.log 2>&1
