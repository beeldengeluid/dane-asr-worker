[![main branch](https://github.com/beeldengeluid/dane-asr-worker/actions/workflows/main-branch.yml/badge.svg)](https://github.com/beeldengeluid/dane-asr-worker/actions/workflows/main-branch.yml)

# dane-asr-worker

DANE worker for processing ASR (optimised for Dutch)

## Switching to Kubernetes

Currently DANE is being made compatible to run in Kubernetes. Here are some invaluable links to get that task done:

- [How to use local docker images in Kubernetes](https://medium.com/bb-tutorials-and-thoughts/how-to-use-own-local-doker-images-with-minikube-2c1ed0b0968)
- [Using codemeta](https://codemeta.github.io/)
- [DNS utils to easily find hostname of services/pods](https://dev.to/vepo/finding-dns-for-kubernetes-service-3p0e)

## Architecture

There are 3 components:

- DANE ASR worker (local Python code)
- Kaldi_NL/ASR Docker container (called via OAS 2.0 API by the worker)
- RabbitMQ Docker container (used for local testing & integration tests without the DANE server)

## Building & running the ASR container

Build the ASR container using:

```
./build-container.sh [IMAGE_NAME]
```

Just choose a name for the docker image. After the build is successful, the image name is put in the environment variable DANE_ASR_IMAGE. If you don't provide a name, the default dane-la-kaldi is used.

Run the ASR container using:

```
./start-container.sh [IMAGE_NAME]
```

Again the IMAGE_NAME is optional. If you do not provide a name the value from DANE_ASR_IMAGE will be used. Otherwise the default dane-la-kaldi is used. So if you actually got the image on your system (check with `docker images`), then that image will be run.


## Configuring the worker

```
RABBITMQ:
    HOST: 'realdanehost' # Use 'dane-rabbit' to use the local RabbitMQ container started via run-local-rabbit-mq-server.sh
    PORT: 5672
    EXCHANGE: 'DANE-ASR-exchange'
    RESPONSE_QUEUE: 'DANE-ASR-response-queue'
    USER: 'guest'
    PASSWORD: 'guest'
ELASTICSEARCH:
    HOST: 'localhost' #make sure to use an existing ES host!
    PORT: 9200
    #USER: 'elastic'
    #PASSWORD: 'changeme'
    SCHEME: 'http'
```

# Kubernetes

All software components are available as docker images and are present in our image registry. Therefore it is possible to go ahead and run the `k8s-dane-asr.yaml` chart after you've prepared your k8s cluster with the `k8s-cluster-requirements.yaml`

## Preparing your k8s cluster

To properly run, the DANE asr environment requires the following from your Kubernetes cluster:

- A persistent volume with at least 20Gb of storage
- A running Elasticsearch cluster that is accessible via a public IP

Now with this in mind, check the contents of the `k8s-cluster-requirements.yaml` and make the necessary changes.

**Note**: the `dnsutils` `Pod` is optional, but is useful for easily figuring out what the DNS name is for each of the `Services` defined in `k8s-dane-asr.yaml`.



## Creating ConfigMaps

Before being able to successfullt run everything in `k8s-dane-asr.yaml` it is necessary to create `ConfigMaps` for the following components:

### DANE ASR worker

**File**: `DANE-asr-worker/config.yml`

```
RABBITMQ:
    HOST: 'dane-rabbitmq-api.default.svc.cluster.local'
    PORT: 5672
    EXCHANGE: 'DANE-exchange'
    RESPONSE_QUEUE: 'DANE-response-queue'
    USER: 'guest' # change this for production mode
    PASSWORD: 'guest' # change this for production mode
ELASTICSEARCH:
    HOST: ['elasticsearch']
    PORT: 9200
    #USER: 'elastic' # change this for production mode
    #PASSWORD: 'changeme' # change this for production mode
    SCHEME: 'http'
ASR_API:
    HOST: 'dane-asr-api.default.svc.cluster.local'
    PORT: 3023
    SIMULATE: false
    WAIT_FOR_COMPLETION: true
FILE_SYSTEM:
    BASE_MOUNT: '/mnt/dane-fs' #'mount' when running locally
    INPUT_DIR: 'input-files'
    OUTPUT_DIR: 'output-files/asr-output'
    USE_DANE_DOWNLOADER: false
```

After you've created this file, create a ConfigMap from it (from this repo's root dir):

```
kubectl create configmap dane-asr-worker-cfg --from-file config.yml
```

**Note**: The `RABBITMQ.HOST` and `ASR_API.HOST` should be fine if you want to run everything as is in the default namespace of your Kubernetes cluster. If however your cluster is somehow differently setup, you can check the DNS names for these two Services with:

```
kubectl exec dnsutils -- nslookup dane-rabbitmq-api
kubectl exec dnsutils -- nslookup dane-asr-api
```

### KaldiNL API

**Repository**: [DANE-kaldi-nl-api](https://github.com/beeldengeluid/DANE-kaldi-nl-api)
**File**: `config/settings.yaml`

```
DEBUG: True
APP_HOST: '0.0.0.0'
APP_PORT: 3023

BASE_FS_MOUNT_DIR: '/mnt/dane-fs' # see Dockerfile

ASR_INPUT_DIR: 'input-files' # must match FILE_SYSTEM.INPUT_DIR (in DANE-asr-worker)
ASR_OUTPUT_DIR: 'output-files/asr-output' # must match FILE_SYSTEM.OUTPUT_DIR (in DANE-asr-worker)
ASR_PACKAGE_NAME: 'asr-features.tar.gz'
ASR_WORD_JSON_FILE: 'words.json'

KALDI_NL_DIR: '/usr/local/opt/kaldi_nl' #'/opt/Kaldi_NL'
KALDI_NL_DECODER: 'decode_OH.sh' #'decode.sh'

PID_CACHE_DIR: 'pid-cache' # relative from the server.py dir

LOG_DIR: 'log' # relative from the server.py dir
LOG_NAME: 'asr-service.log'
LOG_LEVEL_CONSOLE: 'DEBUG' # Levels: NOTSET - DEBUG - INFO - WARNING - ERROR - CRITICAL
LOG_LEVEL_FILE: 'DEBUG' # Levels: NOTSET - DEBUG - INFO - WARNING - ERROR - CRITICAL
```

After you've created this file, create a ConfigMap from it (from this repo's root dir):

```
kubectl create configmap dane-kaldi-api-cfg --from-file {DANE-kaldi-nl-api}/config/settings.yaml
```

### DANE server

The DANE server Pod must be connected to the same RabbitMQ and Elasticsearch as the DANE-asr-worker

**Repository**: [DANE-server](https://github.com/CLARIAH/DANE-server)
**File** `config.yml`


```
DANE:
    API_URL: 'http://localhost:5500/DANE/'
    MANAGE_URL: 'http://localhost:5500/manage/'
RABBITMQ:
    HOST: 'dane-rabbitmq-api.default.svc.cluster.local'
    PORT: 5672
    EXCHANGE: 'DANE-exchange'
    RESPONSE_QUEUE: 'DANE-response-queue'
    USER: 'guest'
    PASSWORD: 'guest'
ELASTICSEARCH:
    HOST: ['elasticsearch']
    PORT: 9200
    USER: 'elastic'
    PASSWORD: 'changeme'
    SCHEME: 'http'
```

After you've created this file, create a ConfigMap from it (assuming you've put it in your local version of DANE-server, but somewhere else is totally fine of course):

```
kubectl create configmap dane-server-cfg --from-file {DANE-server}/config.yml
```

### Creating secret for private registry

**Note** YOU CAN SKIP THIS STEP, SINCE ALL THE REQUIRED IMAGES ARE IN A PUBLIC REPO

In case your docker registry is private, e.g. using AWS ECR, it is necessary to create a k8s `Secret` before the configured `Pods` are able to pull the images from it. You can do this with:

```
kubectl create secret docker-registry xomg-aws-registry --docker-server={aws-server} --docker-username=AWS --docker-password={password}
```

The `{aws-server}` can be found in the `k8s-dane-asr.yaml` and always ends with `.dkr.ecr.eu-west-1.amazonaws.com`.

The `{password}` needs to be requested from our devops engineer.


## Running the DANE ASR environment

After you've created all required `ConfigMaps` you can run the DANE ASR environment using:

```
kubectl apply -f k8s-dane-asr.yaml
```

If you have applied this file before, e.g. for figuring out the DNS name of some of the Services, then it might be possible that some Pods won't be running properly.

In any case it is now good to check if your Pods are all running fine with:

```
kubectl get pods
```

If some Pods are not running properly you can find the cause with these 2 commands:

```
kubectl logs {pod-name}
kubectl describe pod {pod-name}
```

It is very well possible you need to delete the failing Pods and then reapply the `k8s-dane-asr.yaml` again. In some cases this is necessary, since k8s does not always self-heal.

In some cases a Pod won't terminate (after deleting) and it might be necessary to forecefully delete it:

```
kubectl delete pod {pod-name} --grace-period=0 --force
```

# Working on the core images

The following Docker images are available in the beeldengeluid en CLARIAH organisations on GitHub.

In case you require these images to be updated locally, or in the image registry, the following sub sections are worth reading.

### DANE server (API):

The [DANE-server](https://github.com/CLARIAH/DANE-server) consists of 2 different processes, the `TaskScheduler` and a REST API. The `TaskScheduler` is built with:

```
docker build -t dane-server -f Dockerfile.ts .
```

and the API with:

```
docker build -t dane-server-api -f Dockerfile.api .
```

### DANE ASR worker:

The [DANE-asr-worker](https://github.com/beeldengeluid/DANE-asr-worker) receives ASR jobs from the DANE-server and passes them on to the KaldiNL API, which is also [located](https://github.com/beeldengeluid/DANE-asr-worker/blob/kube-arch/asr_api/Dockerfile) in the same repository.

```
docker build -t dane-asr-worker .
```

```
cd asr_api
docker build -t dane-kaldi-api .
```

## Running on your local images

In case you're working on this ASR worker and running your local k8s cluster using minikube, you can run your local dane-asr-worker image by changing `k8s-dane-asr.yaml` in the following way:

```
  containers:
  - name: dane-asr-worker
    image: dane-asr-worker # public.ecr.aws/a0x3r1t1/dane-asr-worker:v1
    imagePullPolicy: Never # Always
```

## Pushing images to the AWS registry

The above `docker build` commands only show how to build the images on your local machine. Whenever an image has been tested well and is ready to be put in the central repository, you can do this in the following way (for e.g. the dane-asr-worker):


```
docker tag dane-asr-worker {aws-ecr-server}/dane-asr-worker:{version}
```

For the {aws-ecr-server} ask your devops engineer.
For `{version}` follow the `{major version}.{minor version}` approach.
