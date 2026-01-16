@echo off
setlocal
if "%USERPROFILE%"=="" (
  echo USERPROFILE is not set. Please set it or run from a standard user shell.
  exit /b 1
)
set "CERT_DIR=%USERPROFILE%\data\letsencrypt\live\localhost"
if not exist "%CERT_DIR%" mkdir "%CERT_DIR%"
openssl genrsa -out "%CERT_DIR%\privkey.pem" 2048
openssl req -new -x509 -key "%CERT_DIR%\privkey.pem" -out "%CERT_DIR%\fullchain.pem" -days 3650 -subj "/CN=localhost" -addext "subjectAltName = DNS:localhost,IP:127.0.0.1"
endlocal
