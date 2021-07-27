#!/bin/sh

# prepare the cluster by creating a volume the ES endpoint (current DANE cluster)

kubectl apply -f k8s-cluster-requirements.yaml


# create the configmaps (first make sure you have these settings!)

kubectl create configmap dane-server-cfg --from-file {DANE-SERVER-HOME}/config.yml
kubectl create configmap dane-download-worker-cfg --from-file {DANE-DOWNLOAD-WORKER-HOME}/config.yml
kubectl create configmap dane-kaldi-api-cfg --from-file {KALDINL-API-HOME}/config/settings.py
kubectl create configmap dane-asr-worker-cfg --from-file config.yml

# create the secret used to access the docker registry in AWS (referred to in imagePullSecrets)

kubectl create secret docker-registry xomg-aws-registry --docker-server={aws-server} --docker-username=AWS --docker-password={password}