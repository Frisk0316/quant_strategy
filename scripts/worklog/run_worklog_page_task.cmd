@echo off
setlocal
cd /d "%~dp0..\.."
if not defined WORKLOG_REPO set "WORKLOG_REPO=%CD%\..\quant_worklog"
set "PYTHON=C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe"
set "SESSIONS_JSON=%TEMP%\quant_worklog_sessions.json"

if not exist "%WORKLOG_REPO%\.git" (
  echo ERROR: quant_worklog clone not found: %WORKLOG_REPO%
  exit /b 1
)
for /f "delims=" %%B in ('git -C "%WORKLOG_REPO%" branch --show-current') do set "WORKLOG_BRANCH=%%B"
if /I not "%WORKLOG_BRANCH%"=="main" (
  echo ERROR: quant_worklog clone must be on main, found %WORKLOG_BRANCH%
  exit /b 1
)

rem Strategies snapshot reads frozen research artifacts only (no DB, no replay).
"%PYTHON%" scripts\worklog\snapshot_strategies.py --out "%WORKLOG_REPO%\strategies.json"
if errorlevel 1 (
  echo WARNING: strategies snapshot failed; publishing worklog without refresh.
)

"%PYTHON%" scripts\worklog\collect_ai_sessions.py --out "%SESSIONS_JSON%"
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHON%" scripts\worklog\publish_worklog_page.py --out-dir "%WORKLOG_REPO%" --sessions-json "%SESSIONS_JSON%"
if errorlevel 1 exit /b %ERRORLEVEL%

git -C "%WORKLOG_REPO%" add -A
if errorlevel 1 exit /b %ERRORLEVEL%
git -C "%WORKLOG_REPO%" diff --cached --quiet
if errorlevel 2 exit /b %ERRORLEVEL%
if not errorlevel 1 exit /b 0

git -C "%WORKLOG_REPO%" commit -m "chore: refresh worklog"
if errorlevel 1 exit /b %ERRORLEVEL%
git -C "%WORKLOG_REPO%" push origin main
exit /b %ERRORLEVEL%
