@echo off
rem ---------------------------------------------------------------------
rem  XingYiCha - WORKSPACE (dev/test) launcher
rem
rem  Runs app.py from THIS folder, not the installed desktop build in
rem  Program Files. Use it to verify code changes immediately - the
rem  desktop build only picks up new code after a rebuild.
rem
rem  Double-click: picks a free port (5001 upward, so it can run next to
rem  the desktop build), waits for /api/ping, then opens the browser.
rem  Close the window or press Ctrl+C to stop.
rem
rem  DEV_PORT=5003      choose a different preferred port
rem  DEV_NO_BROWSER=1   do not open a browser
rem  DEV_PYTHON=...     force a specific interpreter
rem ---------------------------------------------------------------------
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title XingYiCha WORKSPACE test  ^(Ctrl+C to stop^)

cd /d "%~dp0"

rem --- pick an interpreter -------------------------------------------
rem Order matters: a project venv first, then the interpreters whose
rem site-packages actually carry the dependencies. A bare `py -3` is NOT a
rem safe default - it resolves to the newest installed 3.x, which may be a
rem stub with no python.exe (observed here: py -3 -> Python314, missing).
set "PY="
if defined DEV_PYTHON set "PY=%DEV_PYTHON%"
if not defined PY if exist "%~dp0venv\Scripts\python.exe"  set "PY=%~dp0venv\Scripts\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"

rem Verify each candidate really starts before committing to it.
if not defined PY call :try_py "py -3.12"
if not defined PY call :try_py "py -3.11"
if not defined PY call :try_py "py -3.10"
if not defined PY call :try_py "python"
if not defined PY call :try_py "py -3"

if not defined PY (
  echo [x] No usable Python found ^(tried DEV_PYTHON, venv, py -3.12/3.11/3.10, python, py -3^).
  echo     Install Python 3.10+ or create a venv in this folder, then retry.
  echo.
  pause
  exit /b 3
)

echo [i] Python: %PY%
%PY% "%~dp0tools\launch_dev.py" %*
set "RC=%ERRORLEVEL%"

rem Keep the window open only on failure, so the reason stays readable.
if not "%RC%"=="0" (
  echo.
  echo [i] launcher exited with code %RC%
  pause
)
endlocal
exit /b %RC%

rem --- helper: accept a launcher only if it actually starts ------------
rem If no candidate has the hard dependencies, launch_dev.py reports exactly
rem which ones are missing, which is a better message than "no Python".
:try_py
set "_cand=%~1"
%_cand% -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=%_cand%"
exit /b 0
