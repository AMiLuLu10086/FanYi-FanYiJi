@echo off
rem ---------------------------------------------------------------
rem  20x Translation Machine - start the local web server
rem  This batch file is intentionally ASCII-only (see setup_env.bat).
rem  Chinese messages are printed by server.py.
rem ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [run] Virtual environment not found. Running setup first...
    echo.
    call "%~dp0setup_env.bat"
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [run] Setup did not create .venv - please run setup_env.bat and check the errors.
    echo.
    pause
    exit /b 1
)

rem Direct connection to huggingface.co does not work here; use the mirror.
rem The xet transfer channel is extremely slow on that mirror, so disable it.
set "HF_ENDPOINT=https://hf-mirror.com"
set "HF_HOME=%CD%\models"
set "HF_HUB_DISABLE_XET=1"
set "PYTHONUTF8=1"

echo.
echo Opening http://127.0.0.1:8000 in your browser...
echo Keep this window open while using the app. Press Ctrl+C to stop.
echo.
start "" "http://127.0.0.1:8000"

".venv\Scripts\python.exe" -u "server.py"
set "EXITCODE=%ERRORLEVEL%"
echo.
echo [run] server exited with code %EXITCODE%
pause
exit /b %EXITCODE%
