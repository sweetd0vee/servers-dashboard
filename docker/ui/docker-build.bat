#!/usr/bin/env bash

cd ../..

docker build -t arina/sber/dashboard:main -f docker/ui/Dockerfile .
