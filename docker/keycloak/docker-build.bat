@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\.."

docker build -t arina/sber/keycloak:26.4.6 -f docker/keycloak/Dockerfile .
endlocal
