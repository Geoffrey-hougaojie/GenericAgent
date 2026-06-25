@echo off
:: cron_daemon.bat - Hermes-style Gateway launcher (v3.1)
:: Starts cron_daemon.py with pythonw (no window), fully detached
:: Usage: cron_daemon.bat | cron_daemon.bat --stop

set "DAEMON_PY=D:\GenericAgent\sche_tasks\cron_daemon.py"

if "%1"=="--stop" (
    echo [cron_daemon] Sending stop signal...
    "C:\Users\hgj\AppData\Local\Programs\Python\Python312\pythonw.exe" "%DAEMON_PY%" --stop
    timeout /t 2 >nul
    echo Done.
    exit /b
)

echo [cron_daemon] Starting Hermes-style Gateway...
start "" /B "C:\Users\hgj\AppData\Local\Programs\Python\Python312\pythonw.exe" "%DAEMON_PY%" >nul 2>&1
timeout /t 2 >nul
echo [cron_daemon] Started. Check cron_daemon.log for status.
