#!/usr/bin/env bash

cd ../..

docker build -t arina/sber/httpd:2.4 -f docker/httpd/Dockerfile .

#docker push goolegs/trs/keycloak:local
#read -rsn1 -p"Press any key to continue";echo
