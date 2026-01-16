#!/bin/bash


export COMPOSE_PROJECT_NAME=dashboard-ui

docker-compose -f docker-compose.yaml --env-file .env.docker down
