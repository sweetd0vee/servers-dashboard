#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ----postgres------
"$SCRIPT_DIR/../postgres/docker-build.sh"
echo ----app------
"$SCRIPT_DIR/../app/docker-build.sh"
echo ----ui------
"$SCRIPT_DIR/../ui/docker-build.sh"
echo ----httpd------
"$SCRIPT_DIR/../httpd/docker-build.sh"
echo ----keycloak------
"$SCRIPT_DIR/../keycloak/docker-build.sh"
