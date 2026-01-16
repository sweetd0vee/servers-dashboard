@echo off
setlocal
if "%DB_USER%"=="" set "DB_USER=postgres"
psql -v ON_ERROR_STOP=1 --username "%DB_USER%" -c "CREATE DATABASE server_metrics;"
endlocal
