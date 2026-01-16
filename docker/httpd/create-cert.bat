#!/usr/bin/env bash

cd ~
CERT_DIR="./data/letsencrypt/live/localhost"
#CERT_DIR="../../.docker/httpd/data/letsencrypt/live/localhost"
mkdir -p "$CERT_DIR"
openssl genrsa -out "$CERT_DIR/privkey.pem" 2048
openssl req -new -x509 -key "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" -days 3650 -subj "/CN=localhost" -addext "subjectAltName = DNS:localhost,IP:127.0.0.1"