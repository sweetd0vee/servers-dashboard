#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/../postgres/docker-build.sh"
"$SCRIPT_DIR/../app/docker-build.sh"
"$SCRIPT_DIR/../ui/docker-build.sh"
"$SCRIPT_DIR/../httpd/docker-build.sh"
"$SCRIPT_DIR/../keycloak/docker-build.sh"
