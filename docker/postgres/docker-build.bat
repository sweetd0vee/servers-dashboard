@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\.."

docker build -t arina/sber/postgres:16.9-bookworm -f docker/postgres/Dockerfile .
endlocal
