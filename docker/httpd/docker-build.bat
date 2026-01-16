@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\.."

docker build -t arina/sber/httpd:2.4 -f docker/httpd/Dockerfile .
endlocal
