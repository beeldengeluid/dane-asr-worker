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

## Required Docker images

The following Docker images are available in the beeldengeluid en CLARIAH organisations on GitHub. In case you require these images to be updated, the following sub sections are worth reading.

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
# imagePullSecrets:
#    - name: xomg-aws-registry
  containers:
  - name: dane-asr-worker
    image: dane-asr-worker # 917951871879.dkr.ecr.eu-west-1.amazonaws.com/dane-asr-worker:v1
    imagePullPolicy: Never # Always
```

## Pushing images to the AWS registry

The above `docker build` commands only show how to build the images on your local machine. Whenever an image has been tested well and is ready to be put in the central repository, you can do this in the following way (for e.g. the dane-asr-worker):


```
docker tag dane-asr-worker {aws-ecr-server}/dane-asr-worker:{version}
```

For `{version}` follow the `{major version}.{minor version}` approach.


