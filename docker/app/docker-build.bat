@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\.."

docker build -t arina/sber/dashboard-be:main -f docker/app/Dockerfile .
endlocal