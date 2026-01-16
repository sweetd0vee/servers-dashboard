#!/bin/bash


export COMPOSE_PROJECT_NAME=dashboard-tools

docker-compose -f docker-compose.yaml --env-file .env.docker up -d