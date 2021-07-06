#!/bin/sh

REM prepares the k8s cluster


docker build -t dane-asr-worker .

REM download the DANE server and build it

docker build -t dane-server -f Dockerfile.ts .
docker build -t dane-server-api -f Dockerfile.api .

REM prepare the cluster by creating a volume the ES endpoint (current DANE cluster)

kubectl apply -f k8s-cluster-requirements.yaml
