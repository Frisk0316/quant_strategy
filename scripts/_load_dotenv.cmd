@echo off
rem config/settings.yaml keeps storage.timescale_dsn null and load_config() only bridges a
rem process-level DATABASE_URL, so a scheduled wrapper that does not source .env writes
rem nothing and exits 1. That is how 65 hours of forward-only H-039 data were lost between
rem 2026-08-03 and 2026-08-06. Every DB-writing wrapper must call this first.
rem
rem Callers must "cd /d" to the repository root before calling; .env is read relative to the
rem working directory. Uses "call", not "setlocal", so the variable reaches the caller.
rem
rem ponytail: DATABASE_URL only, and no alerting - a stalled task still just shows
rem Last Result 1 in Task Scheduler. Add monitoring if a silent stall costs another window.
if not exist ".env" exit /b 0
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /c:"DATABASE_URL=" ".env"`) do set "DATABASE_URL=%%b"
exit /b 0
