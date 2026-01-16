#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export COMPOSE_PROJECT_NAME=dashboard-tools

docker compose -f "$SCRIPT_DIR/docker-compose.yaml" --env-file "$SCRIPT_DIR/.env.docker" up -d
