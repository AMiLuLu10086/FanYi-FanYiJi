@echo off
rem ---------------------------------------------------------------
rem  20x Translation Machine - environment setup
rem  This batch file is intentionally ASCII-only: cmd.exe decodes
rem  batch files as GBK on Chinese Windows, so UTF-8 Chinese text
rem  here would be executed as garbage commands. All Chinese
rem  messages are printed by setup_env.py instead.
rem ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"

rem Find a Python to run setup_env.py with.
rem Order: PYTHON_HOME env var -> py launcher -> python on PATH.
set "PY="
if defined PYTHON_HOME if exist "%PYTHON_HOME%\python.exe" set "PY=%PYTHON_HOME%\python.exe"
if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 set "PY=py"
)
if not defined PY set "PY=python"

"%PY%" -u "setup_env.py"
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" echo [setup] finished with exit code %EXITCODE%
pause
exit /b %EXITCODE%
