# only when using the k8s-dane-asr-local.yml on a local minikibe (sets the minikube docker env)
# (in this setup ALL required images need to be built in the minikube docker env!)
eval $(minikube docker-env)

# prepare the cluster by creating a volume the ES endpoint (current DANE cluster)

kubectl apply -f k8s-cluster-requirements.yaml


# create the configmaps (first make sure you have these settings!)

kubectl create configmap dane-server-cfg --from-file {DANE-SERVER-HOME}/config.yml
kubectl create configmap dane-download-worker-cfg --from-file {DANE-DOWNLOAD-WORKER-HOME}/config.yml
kubectl create configmap dane-kaldi-api-cfg --from-file {KALDINL-API-HOME}/config/settings.yaml
kubectl create configmap dane-asr-worker-cfg --from-file config.yml

# create the secret used to access the docker registry in AWS (referred to in imagePullSecrets)

kubectl create secret docker-registry xomg-aws-registry --docker-server={aws-server} --docker-username=AWS --docker-password={password}


# login to the ECR
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin {aws-server}


# updating an image in your cluster (e.g. for dane-server-api)

## first set the new image for a deployment
kubectl set image deployments/dane-server-api-deployment dane-server-api=dane-server-api:latest

## then restart the deployment
kubectl rollout restart deployment/dane-server-api-deployment

