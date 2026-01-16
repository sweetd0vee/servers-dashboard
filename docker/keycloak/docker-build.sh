#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

docker build -t arina/sber/keycloak:26.4.6 -f docker-macos/keycloak/Dockerfile .
