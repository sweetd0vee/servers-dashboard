#!/usr/bin/env bash

cd ../..

docker build -t arina/sber/dashboard-be:main -f docker/app/Dockerfile .
