@echo off
setlocal
cd /d "%~dp0.."
if not defined PUBLIC_STATUS_WORKTREE set "PUBLIC_STATUS_WORKTREE=%CD%\..\quant_public_status"

if not exist "%PUBLIC_STATUS_WORKTREE%\.git" (
  echo ERROR: public-status worktree not found: %PUBLIC_STATUS_WORKTREE%
  exit /b 1
)

for /f "delims=" %%B in ('git -C "%PUBLIC_STATUS_WORKTREE%" branch --show-current') do set "PUBLIC_STATUS_BRANCH=%%B"
if /I not "%PUBLIC_STATUS_BRANCH%"=="public-status" (
  echo ERROR: worktree must be on public-status, found %PUBLIC_STATUS_BRANCH%
  exit /b 1
)

"C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe" scripts\publish_public_status.py --out "%PUBLIC_STATUS_WORKTREE%\status.json"
if errorlevel 1 exit /b %ERRORLEVEL%
copy /Y public_status\index.html "%PUBLIC_STATUS_WORKTREE%\index.html" >nul
if errorlevel 1 exit /b %ERRORLEVEL%

git -C "%PUBLIC_STATUS_WORKTREE%" add -A
if errorlevel 1 exit /b %ERRORLEVEL%
git -C "%PUBLIC_STATUS_WORKTREE%" diff --cached --quiet
if errorlevel 2 exit /b %ERRORLEVEL%
if not errorlevel 1 exit /b 0

git -C "%PUBLIC_STATUS_WORKTREE%" commit -m "chore: refresh public status"
if errorlevel 1 exit /b %ERRORLEVEL%
git -C "%PUBLIC_STATUS_WORKTREE%" push origin public-status
exit /b %ERRORLEVEL%
