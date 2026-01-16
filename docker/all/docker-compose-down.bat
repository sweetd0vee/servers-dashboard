@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "COMPOSE_PROJECT_NAME=dashboard-tools"

cd /d "%SCRIPT_DIR%"
docker compose version >NUL 2>NUL
if %ERRORLEVEL%==0 (
  docker compose -f "%SCRIPT_DIR%docker-compose.yaml" down
) else (
  docker-compose -f "%SCRIPT_DIR%docker-compose.yaml" down
)
endlocal
