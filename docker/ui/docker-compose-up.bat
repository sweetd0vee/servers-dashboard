@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "COMPOSE_PROJECT_NAME=dashboard-ui"

cd /d "%SCRIPT_DIR%"
docker compose version >NUL 2>NUL
if %ERRORLEVEL%==0 (
  docker compose -f "%SCRIPT_DIR%docker-compose.yaml" up -d
) else (
  docker-compose -f "%SCRIPT_DIR%docker-compose.yaml" up -d
)
endlocal