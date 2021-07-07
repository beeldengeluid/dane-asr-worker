#!/bin/sh

# prepares the k8s cluster


docker build -t dane-asr-worker .

# download the DANE server and build it

docker build -t dane-server -f Dockerfile.ts .
docker build -t dane-server-api -f Dockerfile.api .

# prepare the cluster by creating a volume the ES endpoint (current DANE cluster)

kubectl apply -f k8s-cluster-requirements.yaml


# create the configmaps (first make sure you have these settings!)

kubectl create configmap dane-asr-worker-cfg --from-file config.yml
kubectl create configmap dane-kaldi-api-cfg --from-file asr_api/config/settings.py