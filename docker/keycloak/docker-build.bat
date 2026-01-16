#!/usr/bin/env bash

cd ../..

docker build -t arina/sber/keycloak:26.4.6 -f docker/keycloak/Dockerfile .
