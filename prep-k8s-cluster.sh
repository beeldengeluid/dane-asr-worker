#!/bin/sh

# prepare the cluster by creating a volume the ES endpoint (current DANE cluster)

kubectl apply -f k8s-cluster-requirements.yaml


# create the configmaps (first make sure you have these settings!)

kubectl create configmap dane-server-cfg --from-file {DANE-SERVER-HOME}/config.yml
kubectl create configmap dane-asr-worker-cfg --from-file config.yml
kubectl create configmap dane-kaldi-api-cfg --from-file asr_api/config/settings.py

# create the secret used to access the docker registry in AWS (referred to in imagePullSecrets)

kubectl create secret docker-registry xomg-aws-registry --docker-server={aws-server} --docker-username=AWS --docker-password={password}