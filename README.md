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