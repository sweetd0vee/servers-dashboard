#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="${HOME}/data/letsencrypt/live/localhost"
mkdir -p "$CERT_DIR"

openssl genrsa -out "$CERT_DIR/privkey.pem" 2048
openssl req -new -x509 -key "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" -days 3650 -subj "/CN=localhost" -addext "subjectAltName = DNS:localhost,IP:127.0.0.1"
