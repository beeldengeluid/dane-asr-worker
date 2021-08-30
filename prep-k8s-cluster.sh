# only when using the k8s-dane-asr-local.yml on a local minikibe (sets the minikube docker env)
# (in this setup ALL required images need to be built in the minikube docker env!)
eval $(minikube docker-env)

# prepare the cluster by creating a volume the ES endpoint (current DANE cluster)

kubectl apply -f k8s-cluster-requirements.yaml

# delete the old configmaps

kubectl delete configmap dane-server-cfg
kubectl delete configmap dane-download-worker-cfg
kubectl delete configmap dane-kaldi-api-cfg
kubectl delete configmap dane-asr-worker-cfg

# create the configmaps (first make sure you have these settings!)

kubectl create configmap dane-server-cfg --from-file ../DANE-server/config.yml
kubectl create configmap dane-download-worker-cfg --from-file ../download-worker/config.yml
kubectl create configmap dane-kaldi-api-cfg --from-file ../DANE-kaldi-nl-api/config/settings.yaml
kubectl create configmap dane-asr-worker-cfg --from-file config.yml

# add videohosting.beng.nl entry to /etc/hosts (download worker)
echo -e "46.23.85.61\tvideohosting.beng.nl" >> /etc/hosts

# create the secret used to access the docker registry in AWS (referred to in imagePullSecrets)

kubectl create secret docker-registry xomg-aws-registry --docker-server={aws-server} --docker-username=AWS --docker-password={password}


# login to the ECR
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin {aws-server}

# updating an image in your cluster (e.g. for dane-server-api)

## first set the new image for a deployment
kubectl set image deployments/dane-server-api-deployment dane-server-api=dane-server-api:latest

## then restart the deployment
kubectl rollout restart deployment/dane-server-api-deployment


# create aws/eks context
aws eks --region eu-west-1 update-kubeconfig --name test-cluster

# switch context (e.g. from minikube to the aws/eks test-cluster)
kubectl config use-context CONTEXT_NAME

# list all contexts
kubectl config get-contexts

# connect to specific container in a pod

kubectl exec -ti dane-asr-worker-deployment-74d9d6c8f8-czbz9 --container kaldi-nl-api -- /bin/bash
kubectl exec -ti dane-asr-worker-deployment-74d9d6c8f8-czbz9 --container dane-asr-worker -- /bin/bash

# read this (debugging pods)

https://kubernetes.io/docs/tasks/debug-application-cluster/debug-running-pod/