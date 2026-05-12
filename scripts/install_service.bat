
@echo off
REM Install AgentSystem as a Windows service using nssm
REM Download nssm from https://nssm.cc/download

SET SERVICE_NAME=AgentSystem
SET PYTHON_PATH=%~dp0.venv\Scripts\pythonw.exe
SET SCRIPT_PATH=%~dp0scripts\run_headless.py
SET LOG_PATH=%~dp0memory\service.log

echo Installing %SERVICE_NAME% as a Windows service...

nssm install %SERVICE_NAME% "%PYTHON_PATH%" "%SCRIPT_PATH%"
nssm set %SERVICE_NAME% AppDirectory "%~dp0"
nssm set %SERVICE_NAME% AppStdout "%LOG_PATH%"
nssm set %SERVICE_NAME% AppStderr "%LOG_PATH%"
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateBytes 10485760
nssm set %SERVICE_NAME% AppRestartDelay 5000
nssm set %SERVICE_NAME% Description "Autonomous multi-agent productivity system"

echo Service installed. Start with: nssm start %SERVICE_NAME%
echo View logs at: %LOG_PATH%
pause
