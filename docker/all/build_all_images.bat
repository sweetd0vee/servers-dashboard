@echo off
setlocal

REM Получаем директорию, где находится этот скрипт
set "SCRIPT_DIR=%~dp0"

REM Переходим в папку postgres
cd /d "%SCRIPT_DIR%..\postgres"

echo Build postgres docker image

REM Показываем текущую директорию
cd

REM Запускаем скрипт сборки
call docker-build.bat

endlocal
pause