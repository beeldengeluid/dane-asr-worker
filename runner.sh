#!/bin/bash

[[ -z "${DANE_DOCKER_IMAGE}" ]] && DANE_DOCKER_IMAGE=${1:-"dane-la-kaldi"} || DANE_DOCKER_IMAGE="${1:DANE_DOCKER_IMAGE}"

#name of the docker container
RABBITMQ_IMAGE="rabbitmq:3-management"
RABBITMQ_MANAGE_PORT=15672
RABBITMQ_PORT=5672
RABBITMQ_CONTAINER="danermq"
RABBITMQ_HOST="dane-rabbit"

echo $DANE_DOCKER_IMAGE

if docker image inspect $DANE_DOCKER_IMAGE &> /dev/null; then
	echo "--- Found the DANE ASR Docker image, starting the local Rabbit MQ server... ---"

	if [ "$( docker container inspect -f '{{.State.Status}}' $RABBITMQ_CONTAINER )" == "running" ]; then
		echo "Great the  RabbitMQ container is already running"

	else
		echo "--- RabbitMQ not running yet, so starting... ---"
		docker run --rm -d \
		--hostname $RABBITMQ_HOST \
		-p $RABBITMQ_MANAGE_PORT:$RABBITMQ_MANAGE_PORT \
		-p $RABBITMQ_PORT:$RABBITMQ_PORT \
		--name $RABBITMQ_CONTAINER $RABBITMQ_IMAGE
	fi

	echo "--- Ok RabbitMQ is running, now creating the DANE exchange... ---"

	python src/dane_rmq_test 0

	echo "--- Ok the DANE exchange is there, now starting the DANE worker... ---"

	python src/worker.py
else
	echo "Please build the DANE ASR Docker image first"

fi